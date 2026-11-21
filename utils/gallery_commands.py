"""Stable gallery command targets, independent of thumbnail ordering."""
import hashlib
import os


def gallery_item_key(path):
    canonical = os.path.normcase(os.path.abspath(os.fspath(path)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deletion_index(command, paths):
    parts = command.split("_")
    if len(parts) >= 3 and parts[:2] == ["DELETE", "KEY"]:
        return next((i for i, path in enumerate(paths)
                     if path and gallery_item_key(path) == parts[2]), -1)
    # Compatibility with already-open pages using the previous command format.
    if len(parts) >= 2 and parts[0] == "DELETE":
        return int(parts[1])
    return -1


def remove_gallery_references(paths, index, *seed_lists):
    """Drop every reference to a deleted file, keeping parallel seeds aligned."""
    key = gallery_item_key(paths[index])
    indices = [i for i, path in enumerate(paths)
               if path and gallery_item_key(path) == key]
    unique_seeds = {id(seeds): seeds for seeds in seed_lists if isinstance(seeds, list)}
    for i in reversed(indices):
        paths.pop(i)
        for seeds in unique_seeds.values():
            if i < len(seeds):
                seeds.pop(i)
