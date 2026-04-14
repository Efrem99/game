import os
import subprocess
import hashlib
from utils.logger import logger
from managers.runtime_data_access import load_data_file

class PiperTTSManager:
    """
    Handles local neural text-to-speech synthesis using the Piper engine.
    Supports audio caching and per-NPC voice profiles.
    """
    def __init__(self, app):
        self.app = app
        self.root = getattr(app, "project_root", os.getcwd())
        self.binary_path = os.path.join(self.root, "tools", "piper", "piper.exe")
        self.models_dir = os.path.join(self.root, "tools", "piper", "models")
        self.cache_dir = os.path.join(self.root, "cache", "audio", "piper")
        self.profiles_path = os.path.join(self.root, "data", "audio", "piper_voices.json")
        
        self._profiles = {}
        self._load_profiles()
        
        # Ensure directories exist
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load_profiles(self):
        payload = load_data_file(self.app, "audio/piper_voices.json", default={})
        if isinstance(payload, dict) and payload:
            self._profiles = payload
        else:
            # Default profiles if file missing
            self._profiles = {
                "default": {
                    "model": "en_GB-ryan-medium.onnx",
                    "speed": 1.0,
                    "noise_scale": 0.667,
                    "noise_w": 0.8
                }
            }

    def get_voice_for_npc(self, npc_id):
        npc_id = str(npc_id).lower()
        if npc_id in self._profiles:
            return self._profiles[npc_id]
        return self._profiles.get("default", {})

    def synthesize(self, text, npc_id="default"):
        """
        Synthesizes text to a WAV file and returns the path.
        Uses cache if the same text and voice profile have been synthesized before.
        """
        text = str(text or "").strip()
        if not text:
            return None

        profile = self.get_voice_for_npc(npc_id)
        model_name = profile.get("model", "en_GB-ryan-medium.onnx")
        model_path = os.path.join(self.models_dir, model_name)
        
        if not os.path.exists(self.binary_path):
            logger.warning(f"[PiperTTS] Piper binary not found at {self.binary_path}")
            return None
        
        if not os.path.exists(model_path):
            logger.warning(f"[PiperTTS] Model not found at {model_path}")
            # Fallback to default if not already default
            if npc_id != "default":
                return self.synthesize(text, "default")
            return None

        # Generate cache key based on text and profile
        hash_input = f"{text}|{model_name}|{profile.get('speed', 1.0)}"
        cache_key = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
        output_path = os.path.join(self.cache_dir, f"{cache_key}.wav")

        if os.path.exists(output_path):
            return output_path

        # Subprocess call to piper
        # piper.exe -m model.onnx -f output.wav
        # Text is passed via stdin
        try:
            cmd = [
                self.binary_path,
                "-m", model_path,
                "-f", output_path
            ]
            
            # Additional params if piper supports them via CLI
            # Note: Piper usually reads speed and other params from the model config, 
            # but some versions support CLI overrides.
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = process.communicate(input=text, timeout=10)
            
            if process.returncode == 0 and os.path.exists(output_path):
                logger.info(f"[PiperTTS] Synthesized: '{text[:20]}...' -> {output_path}")
                return output_path
            else:
                logger.error(f"[PiperTTS] Failed to synthesize: {stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            process.kill()
            logger.error(f"[PiperTTS] Timeout during synthesis of '{text[:20]}...'")
            return None
        except Exception as e:
            logger.error(f"[PiperTTS] Error calling Piper: {e}")
            return None

    def preload_model(self, model_name):
        """Optionally warm up the model (Piper doesn't have a daemon mode by default in this CLI version)"""
        pass
