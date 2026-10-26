"""Track only prompts compiled from a timeline; manually supplied prompts stay independent."""
def prompt_header(saved, timeline, prompt, audio, dictionary, subject=None):
    source = saved.get("video_prompt_source")
    stale = (isinstance(source, dict) and bool(str(prompt or "").strip())
             and prompt == source.get("prompt")
             and (timeline != source.get("timeline") or audio != source.get("audio")
                  or ("subject" in source and (saved.get("sceneggiatura_prompt", "") if subject is None else subject) != source["subject"])))
    title = dictionary.get("prompt_cinema", "Video prompt")
    if stale:
        title += " · " + dictionary.get("video_prompt_stale", "⚠️ Video prompt needs updating")
    return title
