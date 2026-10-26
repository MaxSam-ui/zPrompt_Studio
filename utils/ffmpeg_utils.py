# utils/ffmpeg_utils.py

import os
import sys
import glob
import shutil
import subprocess
import traceback

from core import config, log

_cached_ffmpeg_path = None


def _ottieni_percorso_ffmpeg():
    """Rileva dinamicamente il percorso di FFmpeg cercando nel PATH globale o eseguendo una scansione ricorsiva."""
    global _cached_ffmpeg_path
    if _cached_ffmpeg_path is not None:
        return _cached_ffmpeg_path

    ffmpeg_global = shutil.which("ffmpeg")
    if ffmpeg_global:
        _cached_ffmpeg_path = ffmpeg_global
        return _cached_ffmpeg_path

    for p in sys.path:
        if "site-packages" in p:
            suffix = "-win64*.exe" if os.name == 'nt' else "-*"
            pattern = os.path.join(p, "imageio_ffmpeg", "binaries", f"ffmpeg{suffix}")
            trovati = glob.glob(pattern)
            if trovati:
                _cached_ffmpeg_path = os.path.abspath(trovati[0])
                return _cached_ffmpeg_path

    if config.COMFYUI_DIR:
        suffix = "*.exe" if os.name == 'nt' else "*"
        pattern_embeded = os.path.join(config.COMFYUI_DIR, "python_embeded", "**", f"*ffmpeg*{suffix}")
        trovati_embeded = glob.glob(pattern_embeded, recursive=True)
        if trovati_embeded:
            file_trovati = [f for f in trovati_embeded if os.path.isfile(f)]
            if file_trovati:
                _cached_ffmpeg_path = os.path.abspath(file_trovati[0])
                log.registra(f"[FFmpeg] Bundled executable detected: {_cached_ffmpeg_path}")
                return _cached_ffmpeg_path

        pattern_comfy = os.path.join(config.COMFYUI_DIR, "ComfyUI", "bin", "**", f"*ffmpeg*{suffix}")
        trovati_comfy = glob.glob(pattern_comfy, recursive=True)
        if trovati_comfy:
            file_trovati_comfy = [f for f in trovati_comfy if os.path.isfile(f)]
            if file_trovati_comfy:
                _cached_ffmpeg_path = os.path.abspath(file_trovati_comfy[0])
                log.registra(f"[FFmpeg] Bundled executable detected: {_cached_ffmpeg_path}")
                return _cached_ffmpeg_path

    _cached_ffmpeg_path = "ffmpeg"
    return _cached_ffmpeg_path


def estrai_ultimo_frame_ffmpeg(video_path, output_img_path):
    """Estrae l'ultimo fotogramma esatto da un file MP4/WebM utilizzando nativamente OpenCV, con fallback su FFmpeg."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("OpenCV non riesce ad aprire il video.")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ret = False
        frame = None
        
        if total_frames > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            ret, frame = cap.read()
            
        if not ret or frame is None:
            cap.release()
            cap = cv2.VideoCapture(video_path)
            last_frame = None
            while True:
                r, f = cap.read()
                if not r:
                    break
                last_frame = f
            if last_frame is not None:
                frame = last_frame
                ret = True
                
        cap.release()
        
        if ret and frame is not None:
            cv2.imwrite(output_img_path, frame)
            return os.path.exists(output_img_path)
        else:
            raise Exception("Rilevamento fotogramma vuoto.")
            
    except Exception as e:
        log.registra(f"OpenCV non utilizzabile o fallito ({e}). Uso il fallback nativo FFmpeg...", "WARNING")
        try:
            ffmpeg_bin = _ottieni_percorso_ffmpeg()
            comando = [
                ffmpeg_bin, '-y', '-sseof', '-1', '-i', video_path,
                '-update', '1', '-q:v', '2', output_img_path
            ]
            
            run_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "check": True
            }
            if os.name == 'nt':
                run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                
            subprocess.run(comando, **run_kwargs)
            return os.path.exists(output_img_path)
        except Exception as ex_ff:
            log.registra(f"Estrazione frame fallita anche con fallback FFmpeg: {ex_ff}", "ERROR")
            return False


def fondi_video_mp4_ffmpeg(lista_video, output_finale_path, durata_clip=None):
    """Unisce una serie di clip MP4. Se durata_clip è fornita, applica una dissolvenza incrociata."""
    txt_path = None
    try:
        ffmpeg_bin = _ottieni_percorso_ffmpeg()
        run_kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "check": True
        }
        if os.name == 'nt':
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        num_clips = len(lista_video)
        fade_duration = 0.4
        
        if durata_clip is not None and num_clips > 1 and float(durata_clip) > (fade_duration * 2):
            clip_duration = float(durata_clip)
            log.registra(f"FFmpeg: Detected {num_clips} clips. Starting cinematic crossfade merge (crossfade: {fade_duration}s)...")
            
            try:
                comando = [ffmpeg_bin, '-y']
                for v in lista_video:
                    comando.extend(['-i', v])
                    
                filter_complex = []
                
                # Catena Video
                last_v_out = "[0:v]"
                current_offset = clip_duration - fade_duration
                for i in range(1, num_clips):
                    next_v_in = f"[{i}:v]"
                    next_v_out = f"[v_chain_{i}]" if i < num_clips - 1 else "[v_final]"
                    filter_complex.append(f"{last_v_out}{next_v_in}xfade=transition=fade:duration={fade_duration:.2f}:offset={current_offset:.2f}{next_v_out}")
                    last_v_out = next_v_out
                    current_offset += clip_duration - fade_duration
                    
                # Catena Audio
                last_a_out = "[0:a]"
                for i in range(1, num_clips):
                    next_a_in = f"[{i}:a]"
                    next_a_out = f"[a_chain_{i}]" if i < num_clips - 1 else "[a_final]"
                    filter_complex.append(f"{last_a_out}{next_a_in}acrossfade=d={fade_duration:.2f}{next_a_out}")
                    last_a_out = next_a_out
                    
                filter_complex_str = "; ".join(filter_complex)
                
                comando.extend([
                    '-filter_complex', filter_complex_str,
                    '-map', '[v_final]',
                    '-map', '[a_final]',
                    '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    output_finale_path
                ])
                subprocess.run(comando, **run_kwargs)
                return os.path.exists(output_finale_path)
                
            except subprocess.CalledProcessError:
                log.registra("FFmpeg: Audio track missing or unsupported for acrossfade. Falling back to video-only crossfade...", "WARNING")
                
                comando = [ffmpeg_bin, '-y']
                for v in lista_video:
                    comando.extend(['-i', v])
                    
                filter_complex = []
                last_v_out = "[0:v]"
                current_offset = clip_duration - fade_duration
                for i in range(1, num_clips):
                    next_v_in = f"[{i}:v]"
                    next_v_out = f"[v_chain_{i}]" if i < num_clips - 1 else "[v_final]"
                    filter_complex.append(f"{last_v_out}{next_v_in}xfade=transition=fade:duration={fade_duration:.2f}:offset={current_offset:.2f}{next_v_out}")
                    last_v_out = next_v_out
                    current_offset += clip_duration - fade_duration
                    
                filter_complex_str = "; ".join(filter_complex)
                comando.extend([
                    '-filter_complex', filter_complex_str,
                    '-map', '[v_final]',
                    '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p',
                    output_finale_path
                ])
                subprocess.run(comando, **run_kwargs)
                return os.path.exists(output_finale_path)
        
        log.registra("FFmpeg: Starting standard fast merge (without crossfade)...")
        txt_path = output_finale_path + ".txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for v_path in lista_video:
                path_sicuro = os.path.abspath(v_path).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{path_sicuro}'\n")
        
        comando = [
            ffmpeg_bin, '-y', '-f', 'concat', '-safe', '0', 
            '-i', txt_path, '-c', 'copy', output_finale_path
        ]
        subprocess.run(comando, **run_kwargs)
        return os.path.exists(output_finale_path)
        
    except Exception as e:
        log.registra(f"FFmpeg video merge error: {e}", "WARNING")
        return False
    finally:
        if txt_path and os.path.exists(txt_path):
            try: os.remove(txt_path)
            except: pass
