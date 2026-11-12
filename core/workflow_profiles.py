"""Declarative bindings for supported workflow adapter families.

Profiles describe graph roles, not executable transformations. New node
semantics still require an adapter; renumbering/reconnecting compatible nodes
does not. No guessing from checkpoint filenames.
"""
import json
import copy
from pathlib import Path


MINIMAX_ROLES = {
    'prompt', 'conditioning', 'sampler', 'seed', 'duration', 'output',
    'guider', 'lora_source', 'lora_target', 'first_image',
}
REQUIRED_INPUTS = {
    'prompt': {'text'}, 'conditioning': {'prompt', 'clip', 'vae', 'width', 'height', 'length'},
    'sampler': {'steps', 'scheduler'}, 'seed': {'noise_seed'},
    'duration': {'value'}, 'output': {'frame_rate', 'images'},
    'guider': {'conditioning'}, 'lora_target': {'model'}, 'first_image': {'image'},
}
GENERATED_ROLES = ('last_image', 'middle_image', 'middle_guide', 'lora_1', 'lora_2', 'lora_3')


def profile_path(workflow_path):
    """A same-name sidecar travels with its exported API workflow."""
    return Path(workflow_path).with_suffix('.profile.json')


def validate_graph(workflow):
    if not isinstance(workflow, dict) or not workflow:
        raise ValueError('Workflow must be a nonempty ComfyUI API graph.')
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict) or not node.get('class_type'):
            raise ValueError(f'Invalid API workflow node: {node_id}')
        for name, value in node['inputs'].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                if value[0] not in workflow or value[1] < 0:
                    raise ValueError(f'Broken workflow link: {node_id}.{name} -> {value}')


def load_minimax_profile(workflow_path, workflow):
    path = profile_path(workflow_path)
    custom = path.parent / 'custom' / path.name
    selected = custom if custom.exists() else path
    try:
        profile = json.loads(selected.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read workflow profile {selected}. Supply a matching .profile.json file.') from exc
    if not isinstance(profile, dict) or profile.get('schema_version') != 1 or profile.get('adapter') != 'minimax_dual_clock':
        raise ValueError(f'Unsupported workflow profile: {selected}')
    mode = profile.get('image_mode')
    if mode not in ('native_keyframes', 'references'):
        raise ValueError('Profile image_mode must be native_keyframes or references.')
    if profile.get('prompt_format', 'auto') not in ('auto', 'base', 'reference'):
        raise ValueError('Profile prompt_format must be auto, base or reference.')
    caps = profile.get('capabilities', {})
    required_caps = ('text_to_video', 'first_last_frames', 'reference_images', 'middle_image', 'custom_lora')
    if not isinstance(caps, dict) or any(type(caps.get(k)) is not bool for k in required_caps):
        raise ValueError('Profile must declare each supported capability as true or false.')
    if not caps['first_last_frames' if mode == 'native_keyframes' else 'reference_images']:
        raise ValueError('Profile image_mode conflicts with its declared capabilities.')
    bindings = profile.get('nodes', {})
    if not isinstance(bindings, dict) or set(bindings) != MINIMAX_ROLES:
        raise ValueError('Profile node roles do not match the MiniMax Dual-Clock adapter.')
    validate_graph(workflow)
    ids = {}
    for role, spec in bindings.items():
        if not isinstance(spec, dict) or not isinstance(spec.get('id'), str):
            raise ValueError(f'Invalid profile binding: {role}')
        node_id = spec['id']
        node = workflow.get(node_id)
        if not node or node['class_type'] != spec.get('class_type'):
            raise ValueError(f'Profile {role}: expected {spec.get("class_type")} at node {node_id}. Check the profile.')
        missing = REQUIRED_INPUTS.get(role, set()) - node['inputs'].keys()
        if missing:
            raise ValueError(f'Profile {role}: missing inputs {sorted(missing)} at node {node_id}.')
        ids[role] = node_id
    if len(set(ids.values())) != len(ids):
        raise ValueError('Profile roles must identify distinct nodes.')
    if workflow[ids['conditioning']]['class_type'] != 'MiniMaxH3ReferenceToVideo':
        raise ValueError('This adapter requires a ReferenceToVideo base graph; it applies native keyframes when selected.')
    if workflow[ids['first_image']]['class_type'] != 'LoadImage':
        raise ValueError('This adapter requires LoadImage for its image input role.')
    if mode == 'native_keyframes' and any(
            name.startswith(('ref_videos.', 'ref_audios.', 'ref_video_audios.'))
            for name in workflow[ids['conditioning']]['inputs']):
        raise ValueError('Native keyframe conversion would discard media references. Use references mode for this graph.')
    source_output = profile.get('lora_source_output', 0)
    if type(source_output) is not int or source_output < 0:
        raise ValueError('Invalid lora_source_output index.')
    # Allocate fresh IDs, never delete or overwrite user nodes with similar names.
    occupied = set(workflow)
    for role in GENERATED_ROLES:
        name = 'studio_' + role
        while name in occupied:
            name += '_'
        occupied.add(name)
        ids[role] = name
    profile['resolved_nodes'] = ids
    profile['loaded_from'] = str(selected)
    return profile


def validate_minimax_request(profile, text_only, has_first, has_last, has_middle, has_lora):
    caps = profile['capabilities']
    if text_only or not (has_first or has_last):
        if not caps['text_to_video']:
            raise ValueError('Selected workflow profile does not support text-to-video.')
    if has_middle and not text_only and not caps['middle_image']:
        raise ValueError('Selected workflow profile does not support an intermediate image.')
    if has_lora and not caps['custom_lora']:
        raise ValueError('Selected workflow profile does not support custom LoRA.')


def validate_profile_output(workflow, profile):
    validate_graph(workflow)
    ids = profile['resolved_nodes']
    # A correct ID mapping alone is insufficient: the output must consume the
    # intended prompt, sampling and timing branches.
    seen = set()
    pending = [ids['output']]
    while pending:
        node_id = pending.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        for value in workflow[node_id]['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                pending.append(value[0])
    for role in ('prompt', 'conditioning', 'sampler', 'seed', 'duration'):
        if ids[role] not in seen:
            raise ValueError(f'Profile {role} is disconnected from the selected video output.')


GRAPH_ADAPTERS = {'zimage', 'flux2', 'krea2', 'krea2_edit', 'qwen21_edit', 'ltx25'}
# Stable internal adapter slots, not source workflow IDs. Profiles bind the
# exported graph to these contracts; omitted slots must not silently skip work.
ADAPTER_SLOTS = {
    'zimage': set('1 2 3 4 5 6 7 8 9 10 11 12 15 16 17'.split()),
    'flux2': {str(i) for i in range(1,14)},
    'krea2': set('1 2 3 4 5 6 7 8 9 10 11 15'.split()),
    'krea2_edit': set('1 2 3 4 5 6 7 8 9 10 11 12 13 15 16 17 18'.split()),
    'qwen21_edit': set('52 53 54 56 59 61 62 65 66 68 69'.split()),
    'ltx25': set('1 2 3 4 5 6 7 8 9 11 12 13 14 15 16 17 18 19 22 23 24 25 26 32 33 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51'.split()),
}


def read_graph_profile(workflow_path, workflow, adapter=None):
    """Validate bindings before mapping external node IDs to adapter slots."""
    path = profile_path(workflow_path)
    custom = path.parent / 'custom' / path.name
    selected = custom if custom.exists() else path
    try:
        profile = json.loads(selected.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read workflow profile: {selected}') from exc
    if not isinstance(profile, dict) or profile.get('schema_version') != 1:
        raise ValueError(f'Unsupported profile schema: {selected}')
    if profile.get('adapter') not in GRAPH_ADAPTERS or (adapter and profile['adapter'] != adapter):
        raise ValueError(f'Workflow profile does not match adapter {adapter}: {selected}')
    bindings = profile.get('nodes')
    if not isinstance(bindings, dict) or not {'prompt', 'output'} <= bindings.keys():
        raise ValueError('Profile must declare prompt and output node roles.')
    validate_graph(workflow)
    ids, slots = set(), set()
    for role, spec in bindings.items():
        if not isinstance(spec, dict) or not isinstance(spec.get('id'), str) or not isinstance(spec.get('slot'), str):
            raise ValueError(f'Invalid profile binding: {role}')
        node_id, slot = spec['id'], spec['slot']
        if node_id in ids or slot in slots or not slot.isdigit():
            raise ValueError(f'Duplicate or invalid profile ID/adapter slot: {role}')
        ids.add(node_id); slots.add(slot)
        node = workflow.get(node_id)
        if not node or node['class_type'] != spec.get('class_type'):
            raise ValueError(f'Profile {role}: expected {spec.get("class_type")} at node {node_id}.')
        required = spec.get('required_inputs')
        if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
            raise ValueError(f'Invalid required_inputs for profile role {role}')
        missing = set(required) - node['inputs'].keys()
        if missing:
            raise ValueError(f'Profile {role}: missing inputs {sorted(missing)}.')
    if slots != ADAPTER_SLOTS[profile['adapter']]:
        raise ValueError('Profile adapter slots are incomplete or unsupported. Change source IDs, not adapter slots.')
    prompt_slot, output_slot = ('59', '65') if profile['adapter'] == 'qwen21_edit' else ('5', '9')
    if bindings['prompt']['slot'] != prompt_slot or bindings['output']['slot'] != output_slot:
        raise ValueError('Profile prompt/output roles do not match the adapter contract.')
    capabilities = profile.get('capabilities')
    if not isinstance(capabilities, dict) or any(type(v) is not bool for v in capabilities.values()):
        raise ValueError('Workflow capabilities must be boolean values.')
    profile['loaded_from'] = str(selected)
    return profile


def _remap_graph(graph, mapping):
    result = {}
    for node_id, node in copy.deepcopy(graph).items():
        for key, value in node['inputs'].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                node['inputs'][key] = [mapping.get(value[0], value[0]), value[1]]
        result[mapping.get(node_id, node_id)] = node
    return result


class GraphProfileBinding:
    """A per-request namespace; adapter constants never refer to source IDs.

    Extra user nodes are isolated from reserved/generated adapter slots. The
    output restores original IDs and allocates non-colliding IDs for new nodes.
    """
    def __init__(self, profile, graph):
        self.profile = profile
        self.original_ids = set(graph)
        mapping = {spec['id']: spec['slot'] for spec in profile['nodes'].values()}
        for i, node_id in enumerate(graph):
            if node_id not in mapping:
                mapping[node_id] = f'__profile_extra_{i}'
        self.restore = {slot: node_id for node_id, slot in mapping.items()}
        self.graph = _remap_graph(graph, mapping)

    def finish(self, graph):
        validate_graph(graph)
        bindings = self.profile['nodes']
        start = bindings['output']['slot']
        if start not in graph:
            raise ValueError('Selected workflow output was removed during preparation.')
        pending, reachable = [start], set()
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            for value in graph[node_id]['inputs'].values():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
                    pending.append(value[0])
        if bindings['prompt']['slot'] not in reachable:
            raise ValueError('Profile prompt is disconnected from the output.')
        mapping = dict(self.restore)
        occupied = set(self.original_ids)
        for node_id in graph:
            if node_id in mapping:
                continue
            candidate = node_id
            while candidate in occupied:
                candidate = 'studio_' + candidate
            occupied.add(candidate)
            mapping[node_id] = candidate
        result = _remap_graph(graph, mapping)
        validate_graph(result)
        return result


def prepare_profile_graph(workflow_path, graph, adapter, operation, loras=(), first_last=False, middle=False):
    profile = read_graph_profile(workflow_path, graph, adapter)
    caps = profile['capabilities']
    for capability, needed in ((operation, True), ('first_last_frames', first_last),
                               ('middle_image', middle), ('custom_lora', any(
                                   name and str(name).strip().lower() not in ('-', 'none', 'nessuno') and float(strength) != 0
                                   for name, strength in loras))):
        if needed and not caps.get(capability, False):
            raise ValueError(f'Workflow profile does not support: {capability}')
    binding = GraphProfileBinding(profile, graph)
    return binding.graph, binding


def check_workflow_profile(path, workflow):
    """Unified read-only diagnostics for every shipped profile family."""
    sidecar = profile_path(path)
    custom = sidecar.parent / 'custom' / sidecar.name
    selected = custom if custom.exists() else sidecar
    try:
        data = json.loads(selected.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read workflow profile: {selected}') from exc
    if isinstance(data, dict) and data.get('adapter') == 'minimax_dual_clock':
        profile = load_minimax_profile(path, workflow)
        validate_profile_output(workflow, profile)
        return profile
    profile = read_graph_profile(path, workflow)
    binding = GraphProfileBinding(profile, workflow)
    binding.finish(binding.graph)
    return profile
