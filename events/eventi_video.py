# events/eventi_video.py

from events.eventi_video_timeline import collega_timeline
from events.eventi_video_generazione import collega_generazione


def collega_video(t1, t2, t3, t5, num_lora_vid, stato_generazione, stato_sessione):
    """
    Main entry point for Video Tab interconnections.
    Delegates visual timeline binding and generation processes
    to dedicated modules.
    """
    collega_timeline(t3, stato_sessione)
    collega_generazione(t1, t2, t3, t5, num_lora_vid, stato_generazione, stato_sessione)