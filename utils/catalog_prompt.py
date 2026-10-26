"""Build explicit catalog context without inventing characters or actions."""
EMPTY_VALUES = {'', '-', 'none', 'nessuno', '- none -', '- nessuno -', '- default preset -'}

def is_empty_choice(value):
    return value is None or str(value).strip().lower() in EMPTY_VALUES

def bounded_count(value, maximum=5):
    try: return max(1,min(maximum,int(value)))
    except (TypeError,ValueError): return 1

def assemble_catalog_prompt(subjects, outfit, actions, subject_count, action_count, characters, outfits, catalog_actions):
    cast=[]
    for value in subjects[:bounded_count(subject_count)]:
        if is_empty_choice(value): continue
        name=str(value).strip(); description=str(characters.get(name,name)).strip()
        line=description if description.lower().startswith((name.lower()+':',name.lower()+',')) or name==description else f'{name}: {description}'
        if line not in cast: cast.append(line)
    blocks=[]
    if cast: blocks.append('CHARACTERS / CAST:\n'+'\n'.join('- '+line for line in cast))
    if not is_empty_choice(outfit): blocks.append('ENVIRONMENT & OUTFIT:\n'+str(outfits.get(outfit,outfit)).strip())
    selected=[f'{index}) {catalog_actions.get(value,value)}' for index,value in enumerate(actions[:bounded_count(action_count)],1) if not is_empty_choice(value)]
    if selected: blocks.append('SCENE ACTIONS:\n'+'\n'.join(selected))
    return '\n\n'.join(blocks)
