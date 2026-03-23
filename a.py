"""
Audio Fight Detection System
=============================
Запуск:
  python audio_fight_detector.py --mode demo        # тест на синтетических файлах
  python audio_fight_detector.py --mode mic         # с микрофона
  python audio_fight_detector.py --mode file --input path/to/audio.wav
  python audio_fight_detector.py --mode rtsp --input rtsp://ip/stream
  python audio_fight_detector.py --mode train --data_dir ./audio_data

Установка зависимостей:
  pip install faster-whisper librosa soundfile numpy torch torchaudio
  pip install pyaudio colorama scikit-learn
  apt install ffmpeg  # или brew install ffmpeg на mac
"""

import os
import sys
import time
import json
import queue
import threading
import argparse
import subprocess
import tempfile
import warnings
from pathlib import Path
from collections import deque
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import librosa
import soundfile as sf
from colorama import Fore, Style, init as colorama_init

warnings.filterwarnings("ignore")
colorama_init(autoreset=True)

# ─────────────────────────────────────────────
# КОНФИГ
# ─────────────────────────────────────────────

SAMPLE_RATE     = 16000
WINDOW_SECONDS  = 5       # сколько секунд анализируем за раз
OVERLAP_SECONDS = 2       # перекрытие окон (чтобы не пропустить событие на стыке)
CNN_WEIGHTS     = "audio_cnn_vsd.pt"
WHISPER_MODEL   = "small"  # tiny/base/small/medium — чем больше тем точнее но медленнее

# Пороги для алертов
THRESH_WATCH     = 0.35
THRESH_PRE_FIGHT = 0.60
THRESH_FIGHT     = 0.80

# Маты — дополни своим списком
PROFANITY_RU = {
    "хуй","хуя","хуйня","нахуй","похуй","хуле",
    "ебать","ебал","еблан","ёбаный","заебал","поебать","ёб",
    "пизда","пиздец","пиздить","пиздёж","пиздатый",
    "бля","блять","блядь","блядина",
    "сука","суки","сучара","сучий",
    "мудак","мудила","мудачьё","мудацкий",
    "залупа","долбоёб","ёбтвоюмать","уёбок",
    "убью","зарежу","пришибу","урою","убьёт",  # угрозы физические
    "убивать","пырнуть","морду","башку","бошку"
}
PROFANITY_KZ = {
    "сасқа","сиқым","қотыр","апаңды","анаңды","атаңды","шешеңді"
}
ALL_PROFANITY = PROFANITY_RU | PROFANITY_KZ


# ─────────────────────────────────────────────
# УТИЛИТЫ
# ─────────────────────────────────────────────

def print_header(text: str):
    print(f"\n{Fore.CYAN}{'─'*60}")
    print(f"  {text}")
    print(f"{'─'*60}{Style.RESET_ALL}")

def print_result(level: str, score: float, details: str = ""):
    colors = {
        "normal":    Fore.GREEN,
        "watch":     Fore.YELLOW,
        "pre_fight": Fore.RED,
        "fight":     Fore.RED + Style.BRIGHT,
    }
    icons = {
        "normal":    "✓",
        "watch":     "⚡",
        "pre_fight": "⚠",
        "fight":     "🔴",
    }
    color = colors.get(level, Fore.WHITE)
    icon  = icons.get(level, "?")
    bar_len = int(score * 30)
    bar = "█" * bar_len + "░" * (30 - bar_len)
    print(f"{color}[{icon}] {level.upper():<10} [{bar}] {score:.2f}  {details}{Style.RESET_ALL}")


def audio_to_mel(audio: np.ndarray, sr: int = SAMPLE_RATE,
                 duration: float = WINDOW_SECONDS) -> torch.Tensor:
    """float32 numpy → (1, 128, T) тензор для CNN."""
    target_len = int(sr * duration)
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    else:
        audio = audio[-target_len:]

    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_mels=128, n_fft=1024, hop_length=512, fmax=8000
    )
    mel_db   = librosa.power_to_db(mel, ref=np.max)
    mel_norm = (mel_db - mel_db.mean()) / (mel_db.std() + 1e-8)
    return torch.tensor(mel_norm, dtype=torch.float32).unsqueeze(0).unsqueeze(0)


# ─────────────────────────────────────────────
# МОДЕЛЬ CNN
# ─────────────────────────────────────────────

class AudioAggressionCNN(nn.Module):
    """
    Вход:  (B, 1, 128, T) — мел-спектрограмма
    Выход: (B, 3)          — логиты [normal, pre_fight, fight]
    """
    def __init__(self, num_classes: int = 3):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1,  32,  3, padding=1), nn.BatchNorm2d(32),  nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64,  3, padding=1), nn.BatchNorm2d(64),  nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(128,256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4))
        )
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(256 * 4 * 4, 512), nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x).flatten(1))


# ─────────────────────────────────────────────
# ЭВРИСТИКА (работает без обученной CNN)
# ─────────────────────────────────────────────

def heuristic_aggression_score(audio: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
    """
    Простая эвристика по акустическим признакам.
    Используется когда нет обученной CNN.
    Не точная, но даёт базовое понимание что происходит.
    """
    if len(audio) < sr * 0.5:
        return {"score": 0.0, "label": "normal", "features": {}}

    # 1. Энергия (громкость)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    rms_norm = min(1.0, rms / 0.15)  # нормируем к типичному разговору

    # 2. Zero-crossing rate — высокий = резкие звуки (крики, удары)
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(audio)))
    zcr_norm = min(1.0, zcr / 0.15)

    # 3. Spectral centroid — высокий = высокочастотный контент (крики)
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr)))
    centroid_norm = min(1.0, centroid / 4000.0)

    # 4. Tempo — быстрый темп речи/движений
    try:
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
        tempo_norm = min(1.0, float(tempo) / 180.0)
    except Exception:
        tempo_norm = 0.0

    # 5. Всплески энергии (удары, резкие звуки)
    frame_energy = librosa.feature.rms(y=audio, frame_length=512, hop_length=256)[0]
    if len(frame_energy) > 1:
        energy_spikes = float(np.sum(frame_energy > frame_energy.mean() * 3)) / len(frame_energy)
    else:
        energy_spikes = 0.0

    # Взвешенная сумма
    score = (
        rms_norm      * 0.30 +
        zcr_norm      * 0.20 +
        centroid_norm * 0.20 +
        tempo_norm    * 0.10 +
        energy_spikes * 0.20
    )
    score = float(np.clip(score, 0.0, 1.0))

    return {
        "score": score,
        "features": {
            "rms":           round(rms_norm, 3),
            "zcr":           round(zcr_norm, 3),
            "centroid":      round(centroid_norm, 3),
            "tempo":         round(tempo_norm, 3),
            "energy_spikes": round(energy_spikes, 3),
        }
    }


# ─────────────────────────────────────────────
# WHISPER ДЕТЕКТОР МАТОВ
# ─────────────────────────────────────────────

class ProfanityDetector:
    def __init__(self, model_size: str = WHISPER_MODEL):
        print(f"  Загружаю Whisper {model_size}...", end="", flush=True)
        try:
            from faster_whisper import WhisperModel
            device = "cuda" if torch.cuda.is_available() else "cpu"
            ctype  = "float16" if device == "cuda" else "int8"
            self.model  = WhisperModel(model_size, device=device, compute_type=ctype)
            self.ready  = True
            print(f" {Fore.GREEN}OK{Style.RESET_ALL} (device={device})")
        except ImportError:
            print(f" {Fore.YELLOW}faster-whisper не установлен, пропускаю{Style.RESET_ALL}")
            self.ready = False

    def analyze(self, audio: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
        if not self.ready or len(audio) < sr * 0.5:
            return {"score": 0.0, "found": [], "transcript": "", "threats": []}

        try:
            segments, _ = self.model.transcribe(
                audio,
                language="ru",
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )
            full_text = " ".join(s.text for s in segments).lower()
        except Exception as e:
            return {"score": 0.0, "found": [], "transcript": f"[ошибка: {e}]", "threats": []}

        words   = set(full_text.split())
        found   = list(words & ALL_PROFANITY)
        threats = [w for w in found if w in {"убью","зарежу","пришибу","урою","убьёт","пырнуть"}]

        if not found:
            score = 0.0
        else:
            density = len(found) / max(len(words), 1)
            score   = min(1.0, 0.4 + density * 2.5)

        if threats:
            score = min(1.0, score + 0.35)

        return {
            "score":      float(score),
            "found":      found,
            "transcript": full_text,
            "threats":    threats
        }


# ─────────────────────────────────────────────
# ОСНОВНОЙ АНАЛИЗАТОР
# ─────────────────────────────────────────────

class AudioAnalyzer:
    def __init__(self, cnn_weights: str = CNN_WEIGHTS, whisper_size: str = WHISPER_MODEL):
        print_header("Инициализация AudioAnalyzer")

        self.device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.use_cnn   = False
        self.cnn_model = None

        # CNN — загружаем если есть веса
        if os.path.exists(cnn_weights):
            try:
                self.cnn_model = AudioAggressionCNN(num_classes=3).to(self.device)
                self.cnn_model.load_state_dict(
                    torch.load(cnn_weights, map_location=self.device)
                )
                self.cnn_model.eval()
                self.use_cnn = True
                print(f"  CNN модель:  {Fore.GREEN}загружена из {cnn_weights}{Style.RESET_ALL}")
            except Exception as e:
                print(f"  CNN модель:  {Fore.YELLOW}ошибка загрузки ({e}), использую эвристику{Style.RESET_ALL}")
        else:
            print(f"  CNN модель:  {Fore.YELLOW}не найдена → используется акустическая эвристика{Style.RESET_ALL}")
            print(f"               (запусти --mode train чтобы обучить)")

        # Whisper
        self.profanity = ProfanityDetector(model_size=whisper_size)

    @torch.no_grad()
    def analyze(self, audio: np.ndarray, sr: int = SAMPLE_RATE) -> dict:
        """Главный метод. Возвращает итоговый скор и детали."""
        t0 = time.time()

        # --- Акустический скор (CNN или эвристика) ---
        if self.use_cnn:
            mel = audio_to_mel(audio, sr).to(self.device)
            logits = self.cnn_model(mel)
            probs  = torch.softmax(logits, dim=1)[0].cpu().numpy()
            cnn_score = float(probs[1] + probs[2])  # pre_fight + fight
            cnn_probs = {"normal": float(probs[0]), "pre_fight": float(probs[1]), "fight": float(probs[2])}
            source = "cnn"
        else:
            h = heuristic_aggression_score(audio, sr)
            cnn_score = h["score"]
            cnn_probs = {"heuristic": h["features"]}
            source = "heuristic"

        # --- Whisper скор ---
        profanity = self.profanity.analyze(audio, sr)

        # --- Финальный скор ---
        # Берём максимум — если что-то одно зашкаливает, это уже сигнал
        final_score = max(cnn_score, profanity["score"])

        # Буст если оба сигнала одновременно
        if cnn_score > 0.5 and profanity["score"] > 0.3:
            final_score = min(1.0, final_score * 1.15)

        level = self._score_to_level(final_score)

        return {
            "score":      round(final_score, 3),
            "level":      level,
            "acoustic":   {"score": round(cnn_score, 3), "source": source, "details": cnn_probs},
            "profanity":  profanity,
            "latency_ms": round((time.time() - t0) * 1000, 1)
        }

    def _score_to_level(self, score: float) -> str:
        if score < THRESH_WATCH:     return "normal"
        if score < THRESH_PRE_FIGHT: return "watch"
        if score < THRESH_FIGHT:     return "pre_fight"
        return "fight"


# ─────────────────────────────────────────────
# ЗАХВАТ АУДИО
# ─────────────────────────────────────────────

class MicCapture:
    """Захват с микрофона через pyaudio."""
    def __init__(self, sr: int = SAMPLE_RATE, chunk_ms: int = 100):
        try:
            import pyaudio
            self.pa       = pyaudio.PyAudio()
            self.sr       = sr
            self.chunk    = int(sr * chunk_ms / 1000)
            self.buffer   = deque(maxlen=sr * (WINDOW_SECONDS + OVERLAP_SECONDS))
            self._running = False
            self._stream  = None
            self.ready    = True
        except ImportError:
            print(f"{Fore.YELLOW}pyaudio не установлен: pip install pyaudio{Style.RESET_ALL}")
            self.ready = False

    def start(self):
        import pyaudio
        self._running = True
        self._stream = self.pa.open(
            format=pyaudio.paFloat32, channels=1,
            rate=self.sr, input=True, frames_per_buffer=self.chunk
        )
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                raw = self._stream.read(self.chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32)
                self.buffer.extend(samples.tolist())
            except Exception:
                pass

    def get_window(self) -> np.ndarray:
        buf = list(self.buffer)
        need = self.sr * WINDOW_SECONDS
        if len(buf) < need:
            buf = [0.0] * (need - len(buf)) + buf
        return np.array(buf[-need:], dtype=np.float32)

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self.pa.terminate()


class RTSPCapture:
    """Захват аудио из RTSP через ffmpeg subprocess."""
    def __init__(self, url: str, sr: int = SAMPLE_RATE):
        self.url      = url
        self.sr       = sr
        self.buffer   = deque(maxlen=sr * (WINDOW_SECONDS + OVERLAP_SECONDS))
        self._running = False

    def start(self):
        self._running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        cmd = [
            "ffmpeg", "-i", self.url,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", str(self.sr), "-ac", "1",
            "-f", "s16le", "pipe:1"
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.sr * 2
        )
        chunk_size = self.sr // 10  # 100ms
        while self._running:
            raw = proc.stdout.read(chunk_size * 2)
            if not raw:
                break
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            self.buffer.extend(samples.tolist())
        proc.kill()

    def get_window(self) -> np.ndarray:
        buf  = list(self.buffer)
        need = self.sr * WINDOW_SECONDS
        if len(buf) < need:
            buf = [0.0] * (need - len(buf)) + buf
        return np.array(buf[-need:], dtype=np.float32)

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────
# ОБУЧЕНИЕ CNN
# ─────────────────────────────────────────────

class AudioDataset(torch.utils.data.Dataset):
    """
    Ожидаемая структура:
      data_dir/
        train/
          normal/     ← .wav файлы
          pre_fight/
          fight/
        val/
          normal/
          pre_fight/
          fight/
    """
    LABELS = {"normal": 0, "pre_fight": 1, "fight": 2}

    def __init__(self, data_dir: str, augment: bool = False):
        self.augment = augment
        self.samples = []
        for cls, lbl in self.LABELS.items():
            d = Path(data_dir) / cls
            if not d.exists():
                continue
            for f in list(d.glob("*.wav")) + list(d.glob("*.mp3")):
                self.samples.append((str(f), lbl))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        try:
            audio, sr = librosa.load(path, sr=SAMPLE_RATE, duration=float(WINDOW_SECONDS))
        except Exception:
            audio = np.zeros(SAMPLE_RATE * WINDOW_SECONDS, dtype=np.float32)
        if self.augment:
            audio = self._augment(audio)
        mel = audio_to_mel(audio)
        return mel.squeeze(0), label  # (1, 128, T)

    def _augment(self, audio: np.ndarray) -> np.ndarray:
        import random
        if random.random() < 0.5:
            audio += np.random.randn(len(audio)).astype(np.float32) * 0.004
        if random.random() < 0.4:
            try:
                audio = librosa.effects.pitch_shift(audio, sr=SAMPLE_RATE, n_steps=random.uniform(-2, 2))
            except Exception:
                pass
        if random.random() < 0.4:
            try:
                audio = librosa.effects.time_stretch(audio, rate=random.uniform(0.85, 1.15))
            except Exception:
                pass
        audio *= random.uniform(0.7, 1.3)
        return audio.astype(np.float32)


def train_cnn(data_dir: str, epochs: int = 50, save_path: str = CNN_WEIGHTS):
    print_header("Обучение AudioAggressionCNN")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    train_ds = AudioDataset(f"{data_dir}/train", augment=True)
    val_ds   = AudioDataset(f"{data_dir}/val",   augment=False)

    if len(train_ds) == 0:
        print(f"{Fore.RED}Нет данных в {data_dir}/train/<normal|pre_fight|fight>/")
        print("Создай папки и положи .wav файлы по классам.{Style.RESET_ALL}")
        return

    # Статистика
    for name, lbl in AudioDataset.LABELS.items():
        n = sum(1 for _, l in train_ds.samples if l == lbl)
        print(f"  train/{name}: {n} файлов")

    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=16, shuffle=True,  num_workers=2)
    val_loader   = torch.utils.data.DataLoader(val_ds,   batch_size=16, shuffle=False, num_workers=2)

    model     = AudioAggressionCNN(num_classes=3).to(device)
    weights   = torch.tensor([1.0, 2.5, 2.0]).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val  = 0.0
    print(f"\n{'Epoch':>6} {'Train Loss':>12} {'Val Acc':>10} {'Pre_fight Recall':>18}")
    print("─" * 52)

    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        for mel, labels in train_loader:
            mel, labels = mel.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(mel), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        # Validation
        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for mel, labels in val_loader:
                mel = mel.to(device)
                preds = model(mel).argmax(dim=1).cpu().tolist()
                all_preds.extend(preds)
                all_labels.extend(labels.tolist())

        acc = sum(p == l for p, l in zip(all_preds, all_labels)) / max(len(all_labels), 1)

        # Recall для pre_fight (класс 1)
        tp = sum(1 for p, l in zip(all_preds, all_labels) if p == 1 and l == 1)
        fn = sum(1 for p, l in zip(all_preds, all_labels) if p != 1 and l == 1)
        pf_recall = tp / max(tp + fn, 1)

        scheduler.step()

        if acc > best_val:
            best_val = acc
            torch.save(model.state_dict(), save_path)
            marker = " ← сохранено"
        else:
            marker = ""

        if epoch % 5 == 0 or epoch == epochs - 1:
            print(f"{epoch+1:>6} {total_loss/len(train_loader):>12.4f} {acc:>10.3f} {pf_recall:>18.3f}{marker}")

    print(f"\n{Fore.GREEN}Обучение завершено. Лучший val_acc: {best_val:.3f}")
    print(f"Модель сохранена: {save_path}{Style.RESET_ALL}")


# ─────────────────────────────────────────────
# ДЕМО — синтетические тесты без реальных данных
# ─────────────────────────────────────────────

def generate_test_audio(scenario: str, duration: float = 5.0) -> np.ndarray:
    """Генерируем синтетическое аудио для разных сценариев."""
    sr = SAMPLE_RATE
    n  = int(sr * duration)
    t  = np.linspace(0, duration, n)

    if scenario == "silence":
        return np.zeros(n, dtype=np.float32)

    elif scenario == "normal_speech":
        # Тихий разговор — низкая энергия, размеренный ритм
        audio = np.zeros(n, dtype=np.float32)
        for freq in [200, 400, 600]:  # голосовые гармоники
            audio += 0.02 * np.sin(2 * np.pi * freq * t)
        audio += np.random.randn(n).astype(np.float32) * 0.005
        return audio

    elif scenario == "raised_voice":
        # Повышенный голос — выше энергия и частоты
        audio = np.zeros(n, dtype=np.float32)
        for freq in [300, 600, 1200, 2400]:
            audio += 0.06 * np.sin(2 * np.pi * freq * t)
        audio += np.random.randn(n).astype(np.float32) * 0.02
        # Случайные всплески (жесты, удары кулаком по столу)
        for _ in range(3):
            pos = np.random.randint(0, n - sr // 4)
            burst = np.random.randn(sr // 8).astype(np.float32) * 0.3
            audio[pos:pos + len(burst)] += burst
        return audio

    elif scenario == "fight_sounds":
        # Драка — высокая энергия, случайные удары, крики
        audio = np.random.randn(n).astype(np.float32) * 0.08
        # Удары
        for _ in range(8):
            pos = np.random.randint(0, n - sr // 8)
            impact = np.random.randn(sr // 10).astype(np.float32) * 0.5
            impact *= np.exp(-np.linspace(0, 5, len(impact)))  # затухание
            audio[pos:pos + len(impact)] += impact
        # Крики (высокие частоты, высокая амплитуда)
        for freq in [800, 1600, 3200]:
            audio += 0.12 * np.sin(2 * np.pi * freq * t)
        return audio

    return np.zeros(n, dtype=np.float32)


def run_demo(analyzer: AudioAnalyzer):
    print_header("DEMO — тест на синтетических сценариях")
    print(f"  {Fore.YELLOW}(Whisper на синтетике не даст результата — это нормально.")
    print(f"   CNN/эвристика должна различить сценарии по акустике.){Style.RESET_ALL}\n")

    scenarios = [
        ("silence",      "Тишина"),
        ("normal_speech","Обычный разговор"),
        ("raised_voice", "Повышенный голос (pre-fight?)"),
        ("fight_sounds", "Звуки драки"),
    ]

    for key, description in scenarios:
        audio = generate_test_audio(key)
        result = analyzer.analyze(audio)
        details = ""
        if result["profanity"]["found"]:
            details = f"мат: {result['profanity']['found']}"
        print(f"  {description:<35}", end="")
        print_result(result["level"], result["score"], details)
        print(f"  {Fore.WHITE}  акустика={result['acoustic']['score']:.2f}  "
              f"профанация={result['profanity']['score']:.2f}  "
              f"задержка={result['latency_ms']}мс{Style.RESET_ALL}\n")

    # Тест с реальным аудио файлом если есть
    test_files = list(Path(".").glob("*.wav")) + list(Path(".").glob("*.mp3"))
    if test_files:
        print(f"\n{Fore.CYAN}Найдены аудио файлы в текущей папке:{Style.RESET_ALL}")
        for f in test_files[:5]:  # максимум 5
            try:
                audio, sr = librosa.load(str(f), sr=SAMPLE_RATE, duration=float(WINDOW_SECONDS))
                result = analyzer.analyze(audio)
                print(f"  {f.name:<40}", end="")
                details = f"мат: {result['profanity']['found']}" if result["profanity"]["found"] else ""
                print_result(result["level"], result["score"], details)
                if result["profanity"]["transcript"]:
                    print(f"  {Fore.WHITE}  транскрипт: \"{result['profanity']['transcript'][:80]}\"{Style.RESET_ALL}")
            except Exception as e:
                print(f"  {Fore.RED}Ошибка {f.name}: {e}{Style.RESET_ALL}")


def run_file(analyzer: AudioAnalyzer, filepath: str):
    print_header(f"Анализ файла: {filepath}")

    audio_full, sr = librosa.load(filepath, sr=SAMPLE_RATE)
    duration       = len(audio_full) / SAMPLE_RATE
    print(f"  Длина: {duration:.1f}с | SR: {sr}Hz\n")

    step = int(SAMPLE_RATE * (WINDOW_SECONDS - OVERLAP_SECONDS))
    win  = int(SAMPLE_RATE * WINDOW_SECONDS)
    pos  = 0
    window_idx = 0

    while pos + win <= len(audio_full):
        chunk  = audio_full[pos:pos + win]
        result = analyzer.analyze(chunk)

        t_start = pos / SAMPLE_RATE
        t_end   = (pos + win) / SAMPLE_RATE
        prefix  = f"  [{t_start:5.1f}–{t_end:4.1f}с] "

        print(prefix, end="")
        details = ""
        if result["profanity"]["found"]:
            details = f"найдено: {', '.join(result['profanity']['found'])}"
        print_result(result["level"], result["score"], details)

        if result["profanity"]["transcript"].strip():
            print(f"{'':30}  → \"{result['profanity']['transcript'][:70]}\"")

        pos += step
        window_idx += 1


def run_mic(analyzer: AudioAnalyzer):
    print_header("Режим микрофона — говори в микрофон, Ctrl+C для остановки")

    capture = MicCapture()
    if not capture.ready:
        print(f"{Fore.RED}Невозможно открыть микрофон.{Style.RESET_ALL}")
        return

    capture.start()
    print(f"  {Fore.GREEN}Захват начат. Анализ каждые {WINDOW_SECONDS - OVERLAP_SECONDS}с...{Style.RESET_ALL}\n")

    step_sec  = WINDOW_SECONDS - OVERLAP_SECONDS
    cooldown  = 0

    try:
        while True:
            time.sleep(step_sec)
            audio  = capture.get_window()
            result = analyzer.analyze(audio)

            # Всегда показываем уровень
            ts = time.strftime("%H:%M:%S")
            print(f"  {Fore.WHITE}[{ts}]{Style.RESET_ALL} ", end="")
            details = ""
            if result["profanity"]["found"]:
                details = f"мат: {result['profanity']['found']}"
            print_result(result["level"], result["score"], details)

            if result["profanity"]["transcript"].strip():
                print(f"  {'':12}→ \"{result['profanity']['transcript'][:80]}\"")

            # Алерт
            if result["level"] in ("pre_fight", "fight") and cooldown == 0:
                print(f"\n  {Fore.RED + Style.BRIGHT}{'!'*50}")
                print(f"  ALERT: {result['level'].upper()} (score={result['score']:.2f})")
                print(f"  {'!'*50}{Style.RESET_ALL}\n")
                cooldown = 6  # пауза ~30 сек (6 * 5сек окон)

            cooldown = max(0, cooldown - 1)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Остановлено.{Style.RESET_ALL}")
    finally:
        capture.stop()


def run_rtsp(analyzer: AudioAnalyzer, url: str):
    print_header(f"RTSP режим: {url}")

    capture = RTSPCapture(url)
    capture.start()

    print(f"  Подключаюсь... (жди 3 секунды)\n")
    time.sleep(3)

    step_sec = WINDOW_SECONDS - OVERLAP_SECONDS
    cooldown = 0

    try:
        while True:
            time.sleep(step_sec)
            audio  = capture.get_window()
            result = analyzer.analyze(audio)

            ts = time.strftime("%H:%M:%S")
            print(f"  [{ts}] ", end="")
            details = ""
            if result["profanity"]["found"]:
                details = f"мат: {result['profanity']['found']}"
            print_result(result["level"], result["score"], details)

            if result["level"] in ("pre_fight", "fight") and cooldown == 0:
                print(f"\n  {Fore.RED + Style.BRIGHT}ALERT: {result['level'].upper()}")
                print(f"  score={result['score']:.2f} | {details}{Style.RESET_ALL}\n")
                cooldown = 6

            cooldown = max(0, cooldown - 1)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Остановлено.{Style.RESET_ALL}")
    finally:
        capture.stop()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audio Fight Detector",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--mode", choices=["demo","mic","file","rtsp","train"],
                        default="demo",
                        help=(
                            "demo  — тест на синтетических примерах\n"
                            "mic   — захват с микрофона\n"
                            "file  — анализ аудио/видео файла\n"
                            "rtsp  — живой RTSP поток\n"
                            "train — обучить CNN (нужен датасет)"
                        ))
    parser.add_argument("--input",    type=str, default=None,
                        help="Путь к файлу или RTSP URL")
    parser.add_argument("--data_dir", type=str, default="./audio_data",
                        help="Папка с датасетом для --mode train")
    parser.add_argument("--epochs",   type=int, default=50)
    parser.add_argument("--weights",  type=str, default=CNN_WEIGHTS)
    parser.add_argument("--whisper",  type=str, default=WHISPER_MODEL,
                        choices=["tiny","base","small","medium"],
                        help="Размер Whisper модели")
    args = parser.parse_args()

    print(f"\n{Fore.CYAN + Style.BRIGHT}")
    print("╔══════════════════════════════════════════╗")
    print("║     Audio Fight Detection System         ║")
    print("╚══════════════════════════════════════════╝")
    print(Style.RESET_ALL)

    if args.mode == "train":
        train_cnn(args.data_dir, epochs=args.epochs, save_path=args.weights)
        return

    # Остальные режимы нужен analyzer
    analyzer = AudioAnalyzer(cnn_weights=args.weights, whisper_size=args.whisper)

    if args.mode == "demo":
        run_demo(analyzer)

    elif args.mode == "mic":
        run_mic(analyzer)

    elif args.mode == "file":
        if not args.input:
            print(f"{Fore.RED}Укажи --input путь_к_файлу{Style.RESET_ALL}")
            sys.exit(1)
        run_file(analyzer, args.input)

    elif args.mode == "rtsp":
        if not args.input:
            print(f"{Fore.RED}Укажи --input rtsp://...{Style.RESET_ALL}")
            sys.exit(1)
        run_rtsp(analyzer, args.input)


if __name__ == "__main__":
    main()