import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.gallery_commands import gallery_item_key

ROOT = Path(__file__).resolve().parents[1]


class GalleryDeletionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.paths = [str(self.folder / f"image_{i}.png") for i in range(4)]
        for path in self.paths:
            Path(path).write_bytes(b"test-only disposable image")
        self.saved = {"generation_mode": "Classic (1 Image)"}
        core = types.ModuleType("core")
        core.sessione = types.SimpleNamespace(carica_ultima_sessione=lambda: dict(self.saved),
                                              salva_sessione=self.saved.update)
        core.log = types.SimpleNamespace(registra=lambda *a: None)
        core.lingua = types.SimpleNamespace(LINGUE={"IT": {}, "EN": {}})
        core.config = types.SimpleNamespace()
        self.manager = types.SimpleNamespace(generazione_attiva=False, batch_attivo=False)
        services = types.ModuleType("services")
        services.comfyui_manager = self.manager
        media = types.ModuleType("utils.media_utils")
        for name in ("compila_galleria_html", "compila_striscia_video_html", "depura_nome_file_infinito",
                     "norm_path_sicuro", "calcola_frames_tab_video", "recupera_soggetto_scena",
                     "pulisci_lista_percorsi_galleria"):
            setattr(media, name, lambda *a, **k: "gallery")
        patched = patch.dict("sys.modules", {"core": core, "services": services,
            "utils.media_utils": media, "gradio": types.SimpleNamespace(update=lambda **kw:kw, Warning=lambda *a:None)})
        patched.start()
        self.addCleanup(patched.stop)
        spec = importlib.util.spec_from_file_location("tested_gallery", ROOT / "events/rendering_gallery_sync.py")
        self.gallery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gallery)

    def delete(self, path, state, batch=False):
        command = "DELETE_KEY_" + gallery_item_key(path) + "_123_1"
        fn = self.gallery.gestisci_trigger_galleria_batch_html if batch else self.gallery.gestisci_trigger_galleria_html
        return fn(command, state)

    def test_consecutive_deletes_after_generation_with_duplicate_references(self):
        a,b,c,d = self.paths
        seeds = [10,10,20,30,40]
        state = {"immagini_generate_cumulate":[a,a,b,c,d], "seed_attuali_cumulati":seeds,
                 "seed_attuali":seeds, "percorso_immagine_selezionata":a}
        for path in (a,b,c,d):
            self.delete(path,state)
            self.assertFalse(Path(path).exists())
            self.assertNotIn(path,state["immagini_generate_cumulate"])
        self.assertEqual(state["immagini_generate_cumulate"],[])
        self.assertEqual(seeds,[])
        self.assertIsNone(state["percorso_immagine_selezionata"])

    def test_queued_click_keeps_target_when_indices_shift(self):
        a,b,c,d = self.paths
        state = {"immagini_generate_cumulate":self.paths.copy()}
        self.delete(a,state)
        self.delete(c,state)  # Captured from the original gallery, before its redraw.
        self.assertEqual(state["immagini_generate_cumulate"],[b,d])
        self.assertTrue(Path(b).exists())
        self.assertTrue(Path(d).exists())
        self.delete(a,state)  # Double click must not delete the next image.
        self.assertEqual(state["immagini_generate_cumulate"],[b,d])

    def test_batch_deletes_are_repeatable(self):
        state = {"immagini_generate_batch":self.paths.copy()}
        for path in self.paths:
            self.delete(path,state,batch=True)
            self.assertFalse(Path(path).exists())
        self.assertEqual(state["immagini_generate_batch"],[])

    def test_storyboard_deletion_uses_storyboard_list(self):
        self.saved["generation_mode"] = "Storyboard"
        state = {"lista_frame_storyboard_attivi":self.paths[:2],
                 "immagini_generate_cumulate":self.paths[2:]}
        self.delete(self.paths[0],state)
        self.delete(self.paths[1],state)
        self.assertEqual(state["lista_frame_storyboard_attivi"],[])
        self.assertTrue(Path(self.paths[2]).exists())

    def test_active_generation_keeps_files(self):
        self.manager.generazione_attiva = True
        state = {"immagini_generate_cumulate":self.paths.copy()}
        self.delete(self.paths[0],state)
        self.assertTrue(Path(self.paths[0]).exists())
        self.assertEqual(len(state["immagini_generate_cumulate"]),4)

    def test_unknown_target_never_deletes_another_image(self):
        state = {"immagini_generate_cumulate":self.paths.copy()}
        self.delete(str(self.folder / "not-in-gallery.png"),state)
        self.assertEqual(state["immagini_generate_cumulate"],self.paths)
