#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "bottle>=0.13.4",
#   "matplotlib>=3.10.3",
#   "numpy>=2.3.1",
#   "scipy>=1.16.0",
#   "sounddevice>=0.4.0",
# ]
# ///
"""Small Bottle demo app for exploring the birdsong modem."""

from __future__ import annotations

import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
birdsong = importlib.import_module("birdsong")

try:
    import bottle
    from bottle import Bottle, redirect, request, response, static_file, template
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only when missing dep
    raise SystemExit(
        "Bottle is not installed. Run `uv sync` and then `just demo`."
    ) from exc

ARTIFACT_ROOT = Path("/tmp/birdsong-demo")
DEFAULT_TEXT = "hello birdsong"
DEFAULT_OPTIONS = {
    "bit_duration": "0.05",
    "freq0": "196.0",
    "freq1": "1760.0",
    "freq_start": "4186.01",
}

PAGE_TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Birdsong Demo</title>
  <style>
    :root {
      --bg: #f5efe2;
      --ink: #1f1f1a;
      --muted: #6c675b;
      --panel: rgba(255, 252, 244, 0.9);
      --line: rgba(78, 64, 44, 0.16);
      --accent: #c2572d;
      --accent-dark: #8e3214;
      --good: #2b6a41;
      --bad: #8e2c2c;
      --shadow: 0 14px 40px rgba(56, 42, 24, 0.12);
      --section-gap: 14px;
      --mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
      --sans: "Avenir Next", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(194, 87, 45, 0.14), transparent 32%),
        linear-gradient(180deg, #fbf7ee 0%, var(--bg) 100%);
    }
    .shell {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }
    .hero {
      display: grid;
      gap: 16px;
      margin-bottom: 28px;
      padding: 28px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }
    h1, h2, h3, p { margin: 0; }
    h1 {
      font-size: clamp(2rem, 4vw, 3.5rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
      max-width: 10ch;
    }
    .lede {
      max-width: 72ch;
      color: var(--muted);
      line-height: 1.55;
      font-size: 1.02rem;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .hero-actions form { margin: 0; }
    .layout {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }
    .layout > *,
    .result,
    .card,
    .asset-grid > *,
    .card > *,
    .result-header > *,
    .meta-grid > * {
      min-width: 0;
    }
    .stack {
      display: grid;
      gap: 18px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 20px;
      display: grid;
      gap: var(--section-gap);
    }
    .card h2 {
      font-size: 1.2rem;
      letter-spacing: -0.02em;
    }
    .card p {
      color: var(--muted);
      line-height: 1.45;
    }
    .section-block {
      display: grid;
      gap: var(--section-gap);
      min-width: 0;
      align-content: start;
      padding-bottom: 20px;
    }
    .section-block > h3 {
      margin: 0;
      line-height: 1.05;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 0.95rem;
      color: var(--muted);
    }
    textarea, input[type="text"], input[type="number"], input[type="file"] {
      width: 100%;
      border: 1px solid rgba(83, 68, 44, 0.22);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
      font: inherit;
    }
    textarea {
      min-height: 140px;
      resize: vertical;
      font-family: var(--mono);
      font-size: 0.95rem;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    button,
    .button-link {
      border: 0;
      border-radius: 999px;
      padding: 11px 18px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
    }
    button.secondary,
    .button-link.secondary {
      background: rgba(31, 31, 26, 0.08);
      color: var(--ink);
    }
    .result {
      display: grid;
      gap: 18px;
      min-width: 0;
    }
    .result-header {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      min-width: 0;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.84rem;
      background: rgba(31, 31, 26, 0.06);
      color: var(--muted);
    }
    .pill.good { color: var(--good); background: rgba(43, 106, 65, 0.12); }
    .pill.bad { color: var(--bad); background: rgba(142, 44, 44, 0.12); }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 10px;
    }
    .meta {
      padding: 12px;
      border-radius: 14px;
      background: rgba(31, 31, 26, 0.04);
    }
    .meta strong {
      display: block;
      font-size: 0.78rem;
      color: var(--muted);
      margin-bottom: 4px;
    }
    code, pre {
      font-family: var(--mono);
      font-size: 0.9rem;
    }
    pre {
      margin: 0;
      padding: 14px;
      border-radius: 16px;
      overflow: auto;
      max-width: 100%;
      background: #191816;
      color: #f7f2e6;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .bits {
      display: flex;
      flex-wrap: wrap;
      gap: 3px;
    }
    .bit {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      width: 18px;
      height: 22px;
      border-radius: 6px;
      font-family: var(--mono);
      font-size: 0.76rem;
      background: rgba(31, 31, 26, 0.08);
      color: var(--muted);
    }
    .bit.one {
      background: rgba(194, 87, 45, 0.18);
      color: var(--accent-dark);
    }
    .bit.handshake {
      background: rgba(43, 106, 65, 0.18);
      color: var(--good);
    }
    .bit.checksum {
      background: rgba(90, 70, 160, 0.18);
      color: #5a46a0;
    }
    .protocol-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 0.84rem;
      color: var(--muted);
    }
    .protocol-legend span {
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .protocol-legend .swatch {
      width: 12px;
      height: 12px;
      border-radius: 4px;
      display: inline-block;
    }
    .byte-group {
      display: flex;
      flex-direction: column;
      gap: 3px;
      align-items: center;
    }
    .byte-group .bits {
      gap: 2px;
    }
    .byte-label {
      font-family: var(--mono);
      font-size: 0.72rem;
      color: var(--muted);
    }
    .protocol-groups {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: flex-end;
    }
    .asset-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr;
      min-width: 0;
    }
    img {
      width: 100%;
      max-width: 100%;
      max-height: 440px;
      display: block;
      object-fit: contain;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: white;
    }
    audio {
      width: 100%;
    }
    a {
      color: var(--accent-dark);
      text-decoration: none;
      font-weight: 600;
    }
    details {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: rgba(31, 31, 26, 0.03);
    }
    summary {
      cursor: pointer;
      font-weight: 600;
    }
    .volume-row {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--muted);
    }
    .volume-row input[type="range"] {
      flex: 1;
      min-width: 0;
    }
    .spectrogram-frame {
      width: 100%;
      max-width: 100%;
      overflow: hidden;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: white;
      padding: 6px;
    }
    .card,
    .result,
    .result-header,
    .meta-grid,
    .asset-grid {
      overflow: hidden;
    }
    .empty {
      min-height: 520px;
      place-items: center;
      text-align: center;
      color: var(--muted);
      background:
        linear-gradient(135deg, rgba(194, 87, 45, 0.06), rgba(31, 31, 26, 0.02)),
        var(--panel);
    }
    .empty strong {
      display: block;
      margin-bottom: 8px;
      color: var(--ink);
      font-size: 1.1rem;
    }
    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
      .empty { min-height: 240px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div>
        <div class="pill">Bottle demo over the real CLI</div>
      </div>
      <h1>Birdsong in one browser tab.</h1>
      <p class="lede">
        This page shells out to the real <code>birdsong.py</code> encode/decode commands,
        stores artifacts in <code>/tmp/birdsong-demo</code>, and gives you a quick visual
        feel for the protocol with audio playback, decode output, and spectrograms.
      </p>
      <div class="hero-actions">
        <form method="post" action="/demo">
          <button type="submit">Show Me How It Works</button>
        </form>
        <a class="button-link secondary" href="/spectro-preview">Open Spectro Preview</a>
        <div class="pill">Try <code>hello birdsong</code>, upload a WAV, or compare the CLI below.</div>
      </div>
    </section>

    <section class="layout">
      <div class="stack">
        <form method="post" action="/encode" class="card">
          <h2>Encode Text</h2>
          <p>Generate a WAV with the real modem and get an immediate decode and spectrogram.</p>
          <label>
            Message
            <textarea name="message">{{message}}</textarea>
          </label>
          <div class="grid">
            <label>Bit duration
              <input type="number" step="0.001" min="0.001" name="bit_duration" value="{{options['bit_duration']}}">
            </label>
            <label>Freq 0
              <input type="text" name="freq0" value="{{options['freq0']}}">
            </label>
            <label>Freq 1
              <input type="text" name="freq1" value="{{options['freq1']}}">
            </label>
            <label>Handshake
              <input type="text" name="freq_start" value="{{options['freq_start']}}">
            </label>
          </div>
          <button type="submit">Generate Demo</button>
        </form>

        <form method="post" action="/decode" enctype="multipart/form-data" class="card">
          <h2>Decode WAV</h2>
          <p>Upload a WAV file and run it through the real decoder. You still get the spectrogram and raw stderr.</p>
          <label>
            WAV file
            <input type="file" name="audio_file" accept=".wav,audio/wav">
          </label>
          <button type="submit" class="secondary">Decode Upload</button>
        </form>
      </div>

      % if result:
      <div class="result" id="result">
        <article class="card">
          <div class="section-block">
            <div class="result-header">
              <h2>{{result['title']}}</h2>
              <div>
                <span class="pill {{'good' if result['ok'] else 'bad'}}">{{'OK' if result['ok'] else 'Needs Attention'}}</span>
                <span class="pill">{{result['kind']}}</span>
              </div>
            </div>
            <p>{{result['summary']}}</p>
            <div class="meta-grid">
            <div class="meta"><strong>Bytes</strong>{{result['metadata']['byte_count']}}</div>
            <div class="meta"><strong>Duration</strong>{{result['metadata']['duration']}}</div>
            <div class="meta"><strong>Sample rate</strong>{{result['metadata']['sample_rate']}}</div>
            <div class="meta"><strong>Artifacts</strong><a href="{{result['audio_url']}}">WAV</a> · <a href="{{result['spectrogram_url']}}">PNG</a></div>
            </div>
          </div>

          % if result.get('decoded_text'):
          <div class="section-block">
            <h3>Decoded Text</h3>
            <pre>{{result['decoded_text']}}</pre>
          </div>
          % end

          % if result.get('bit_html'):
          <div class="section-block">
            <h3>Payload Bits</h3>
            <div class="bits">{{!result['bit_html']}}</div>
            % if result.get('protocol_html'):
            <details>
              <summary>Go Deeper</summary>
              <div class="section-block" style="margin-top: 12px;">
                <div class="protocol-legend">
                  <span><span class="swatch" style="background: rgba(43, 106, 65, 0.18);"></span> Handshake (2 tones at {{options['freq_start']}} Hz)</span>
                  <span><span class="swatch" style="background: rgba(194, 87, 45, 0.18);"></span> Payload (1 = {{options['freq1']}} Hz)</span>
                  <span><span class="swatch" style="background: rgba(31, 31, 26, 0.08);"></span> Payload (0 = {{options['freq0']}} Hz)</span>
                  <span><span class="swatch" style="background: rgba(90, 70, 160, 0.18);"></span> Checksum (sum of all payload bytes mod 256)</span>
                </div>
                <div class="protocol-groups">{{!result['protocol_html']}}</div>
                <p>Each bit is one FSK tone lasting {{options['bit_duration']}}s. No framing header, no error correction &mdash; just handshake, payload, and a single checksum byte.</p>
              </div>
            </details>
            % end
          </div>
          % end

          % if result.get('audio_url') and result.get('spectrogram_url'):
          <div class="asset-grid">
            <div class="section-block">
              <h3>Listen</h3>
              <label class="volume-row">
                Playback volume
                <input id="volume-control" type="range" min="0" max="100" step="1" value="10">
                <span id="volume-value">10%</span>
              </label>
              <p>Starts at a low volume because the modem tones can be sharp and surprisingly loud on laptop speakers.</p>
              <audio controls src="{{result['audio_url']}}"></audio>
            </div>
            <div class="section-block">
              <h3>Spectrogram</h3>
              <div class="spectrogram-frame">
                <img src="{{result['spectrogram_url']}}" alt="Generated spectrogram">
              </div>
            </div>
          </div>
          % end

          <div class="section-block">
            <h3>Equivalent CLI</h3>
            <pre>{{result['cli']}}</pre>
          </div>

          % if result.get('stderr'):
          <details>
            <summary>CLI stderr</summary>
            <pre>{{result['stderr']}}</pre>
          </details>
          % end
        </article>
      </div>
      % else:
      <div class="card empty">
        <div>
          <strong>No demo run yet.</strong>
          Click <em>Show Me How It Works</em> for the quickest first-run path, or generate your own text transmission.
        </div>
      </div>
      % end
    </section>
  </div>
  <script>
    (() => {
      const slider = document.getElementById("volume-control");
      const value = document.getElementById("volume-value");
      const audios = Array.from(document.querySelectorAll("audio"));
      if (!slider || audios.length === 0) return;

      const stored = window.localStorage.getItem("birdsong-demo-volume");
      const initial = stored ?? "10";
      slider.value = initial;

      const applyVolume = (raw) => {
        const numeric = Math.max(0, Math.min(100, Number(raw)));
        const volume = numeric / 100;
        audios.forEach((audio) => { audio.volume = volume; });
        value.textContent = `${numeric}%`;
        window.localStorage.setItem("birdsong-demo-volume", String(numeric));
      };

      applyVolume(initial);
      slider.addEventListener("input", (event) => applyVolume(event.target.value));
    })();
  </script>
</body>
</html>
"""

SPECTRO_PREVIEW_TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Birdsong Spectro Preview</title>
  <style>
    :root {
      --bg: #f5efe2;
      --ink: #1f1f1a;
      --muted: #6c675b;
      --panel: rgba(255, 252, 244, 0.94);
      --line: rgba(78, 64, 44, 0.16);
      --accent: #c2572d;
      --accent-dark: #8e3214;
      --good: #2b6a41;
      --blue: #315f9a;
      --shadow: 0 14px 40px rgba(56, 42, 24, 0.12);
      --mono: "SFMono-Regular", "Menlo", "Consolas", monospace;
      --sans: "Avenir Next", "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(194, 87, 45, 0.14), transparent 32%),
        linear-gradient(180deg, #fbf7ee 0%, var(--bg) 100%);
    }

    a {
      color: var(--accent-dark);
      font-weight: 700;
      text-decoration: none;
    }

    .shell {
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 42px;
      display: grid;
      gap: 18px;
    }

    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      color: var(--muted);
      font-size: 0.92rem;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(320px, 460px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }

    .phone {
      max-width: 460px;
      width: 100%;
      min-height: min(820px, calc(100vh - 112px));
      margin: 0 auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .spectrogram-wrap {
      position: relative;
      height: 238px;
      background: #eee9df;
      overflow: hidden;
      border-bottom: 1px solid var(--line);
    }

    canvas {
      width: 100%;
      height: 100%;
      display: block;
      image-rendering: pixelated;
    }

    .spectrogram-controls {
      position: absolute;
      left: 12px;
      top: 10px;
      display: flex;
      gap: 6px;
      align-items: center;
    }

    .spectrogram-label {
      font-size: 12px;
      color: rgba(31, 31, 26, 0.72);
      background: rgba(255, 252, 244, 0.82);
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid rgba(78, 64, 44, 0.12);
    }

    .spectrogram-label.active {
      background: rgba(43, 106, 65, 0.18);
      color: var(--good);
      border-color: rgba(43, 106, 65, 0.25);
    }

    .spectrogram-label[role="button"] {
      cursor: pointer;
    }

    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 14px 18px;
      font-size: 18px;
      border-bottom: 1px solid var(--line);
    }

    .status-dot {
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background: var(--blue);
      opacity: 0.88;
    }

    .tip {
      margin: 0;
      padding: 16px 18px 32px;
      background: #eef3f2;
      color: #283733;
      font-size: 16px;
      line-height: 1.38;
      border-bottom: 1px solid var(--line);
      min-height: 94px;
    }

    .bird-list {
      flex: 1;
      overflow: auto;
    }

    .bird {
      display: grid;
      grid-template-columns: 88px 1fr 48px;
      gap: 14px;
      align-items: center;
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      min-height: 78px;
    }

    .bird.highlight {
      background: #fff7a8;
    }

    .thumb {
      width: 88px;
      height: 60px;
      border-radius: 7px;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(43, 106, 65, 0.28), rgba(49, 95, 154, 0.28)),
        linear-gradient(180deg, #fbf7ee, #d9d2c3);
      display: grid;
      place-items: center;
      color: rgba(31, 31, 26, 0.72);
      font-family: var(--mono);
      font-size: 0.82rem;
      font-weight: 700;
    }

    .name {
      font-size: 21px;
      line-height: 1.05;
      margin-bottom: 4px;
    }

    .highlight .name {
      font-weight: 800;
    }

    .latin {
      font-size: 15px;
      font-style: italic;
      color: var(--muted);
    }

    .score {
      text-align: right;
      font-variant-numeric: tabular-nums;
      color: #444;
      font-size: 14px;
    }

    .controls {
      padding: 18px;
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 14px;
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.55);
    }

    .status {
      font-size: 13px;
      color: var(--muted);
      line-height: 1.25;
    }

    .record {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      border: 0;
      background: var(--accent);
      color: white;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.14);
      cursor: pointer;
    }

    .record:not(.running)::before {
      content: "";
      display: inline-block;
      width: 29px;
      height: 29px;
      border-radius: 50%;
      background: white;
      vertical-align: -4px;
    }

    .record.running::before {
      content: "";
      display: inline-block;
      width: 24px;
      height: 24px;
      border-radius: 5px;
      background: white;
      vertical-align: -3px;
    }

    .timer {
      font-size: 18px;
      font-weight: 800;
      text-align: right;
      font-variant-numeric: tabular-nums;
      background: #fff;
      padding: 12px;
      border-radius: 12px;
      border: 1px solid rgba(78, 64, 44, 0.12);
    }

    .nav {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      padding: 10px 0 12px;
      border-top: 1px solid var(--line);
      background: #fff;
      color: #8a8d8f;
      text-align: center;
      font-size: 12px;
    }

    .nav div:first-child {
      color: var(--good);
      font-weight: 700;
    }

    .nav-icon {
      display: block;
      width: 26px;
      height: 20px;
      margin: 0 auto 4px;
      font-family: var(--mono);
      font-size: 15px;
      line-height: 20px;
    }

    .notes {
      display: grid;
      gap: 16px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 20px;
      display: grid;
      gap: 12px;
    }

    .pill {
      width: fit-content;
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.84rem;
      background: rgba(31, 31, 26, 0.06);
      color: var(--muted);
    }

    h1, h2, p { margin: 0; }

    h1 {
      font-size: clamp(2rem, 4vw, 3.5rem);
      line-height: 0.95;
      max-width: 10ch;
    }

    h2 {
      font-size: 1.12rem;
      line-height: 1.15;
    }

    p {
      color: var(--muted);
      line-height: 1.5;
    }

    code {
      font-family: var(--mono);
      font-size: 0.92em;
      color: var(--accent-dark);
    }

    @media (max-width: 900px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .phone {
        min-height: 760px;
      }
    }

    @media (max-width: 420px) {
      .shell {
        padding: 18px 10px 28px;
      }

      .phone {
        border-radius: 18px;
      }

      .spectrogram-wrap {
        height: 196px;
      }

      .bird {
        grid-template-columns: 78px 1fr 42px;
        gap: 10px;
      }

      .thumb {
        width: 78px;
        height: 56px;
      }

      .name {
        font-size: 19px;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <div class="topbar">
      <a href="/">Birdsong Demo</a>
      <span>Browser-only companion preview</span>
    </div>

    <section class="layout">
      <div class="phone">
        <div class="spectrogram-wrap">
          <canvas id="spectrogram"></canvas>
          <div class="spectrogram-controls">
            <div class="spectrogram-label" id="btn-linear" role="button" tabindex="0">Linear</div>
            <div class="spectrogram-label active" id="btn-mel" role="button" tabindex="0">Mel</div>
          </div>
        </div>

        <div class="controls">
          <div class="status" id="status">Ready. Works best over HTTPS or localhost.</div>
          <button class="record" id="record" aria-label="Start or stop microphone preview"></button>
          <div class="timer" id="timer">00:00</div>
        </div>

        <div class="section-title">
          <span>Best suggestions</span>
          <span class="status-dot"></span>
        </div>

        <p class="tip" id="tip">Press record and allow microphone access. This preview uses simple spectral heuristics, not a trained bird model.</p>

        <section class="bird-list" id="birdList"></section>

        <nav class="nav" aria-label="Preview tabs">
          <div><span class="nav-icon">ID</span>Identify</div>
          <div><span class="nav-icon">EX</span>Explore</div>
          <div><span class="nav-icon">LL</span>Life List</div>
          <div><span class="nav-icon">ST</span>Settings</div>
        </nav>
      </div>

      <aside class="notes">
        <article class="card">
          <div class="pill">Companion concept</div>
          <h1>Spectrogram-first bird ID preview.</h1>
          <p>
            This is a self-contained browser sketch derived from the downloaded
            prototype. It is intentionally separate from the supported acoustic
            modem path, which still lives on the main demo and calls
            <code>birdsong.py</code>.
          </p>
        </article>

        <article class="card">
          <h2>What is real here</h2>
          <p>
            The microphone capture and scrolling spectrogram use the Web Audio
            API. The ranked suggestions are only deterministic band-energy
            heuristics so the UI can be tested without model assets or network
            calls.
          </p>
        </article>

        <article class="card">
          <h2>Integration boundary</h2>
          <p>
            Served by <code>just demo</code> at <code>/spectro-preview</code>.
            No files are written, no modem constants are changed, and no
            unsupported classifier is added to the production surface.
          </p>
        </article>
      </aside>
    </section>
  </main>

  <script>
    const birds = [
      {
        id: "steller",
        common: "Steller's Jay",
        latin: "Cyanocitta stelleri",
        tag: "SJ",
        tip: "Listen for harsh, scratchy calls. Often loud and conspicuous in conifers."
      },
      {
        id: "goose",
        common: "Canada Goose",
        latin: "Branta canadensis",
        tag: "CG",
        tip: "Low honks and repeated calls. Often heard from open water or overhead flocks."
      },
      {
        id: "wren",
        common: "Bewick's Wren",
        latin: "Thryomanes bewickii",
        tag: "BW",
        tip: "Listen for bright, varied phrases from shrubs, hedges, and brushy edges."
      },
      {
        id: "junco",
        common: "Dark-eyed Junco",
        latin: "Junco hyemalis",
        tag: "DJ",
        tip: "Look for those white tail feathers as they fly away."
      },
      {
        id: "finch",
        common: "House Finch",
        latin: "Haemorhous mexicanus",
        tag: "HF",
        tip: "Listen for a lively, warbling song, often near houses, wires, and feeders."
      },
      {
        id: "sparrow",
        common: "Song Sparrow",
        latin: "Melospiza melodia",
        tag: "SS",
        tip: "Song often starts with repeated notes, then moves into a buzzy phrase."
      }
    ];

    const birdList = document.getElementById("birdList");
    const tipEl = document.getElementById("tip");
    const statusEl = document.getElementById("status");
    const timerEl = document.getElementById("timer");
    const button = document.getElementById("record");
    const canvas = document.getElementById("spectrogram");
    const ctx = canvas.getContext("2d");

    const btnLinear = document.getElementById("btn-linear");
    const btnMel = document.getElementById("btn-mel");

    let audioContext = null;
    let analyser = null;
    let source = null;
    let stream = null;
    let running = false;
    let startedAt = 0;
    let raf = null;
    let freqData = null;
    let scoreState = new Map();
    let useMel = true;
    let melBinMap = null;

    // Magma-inspired color map (256 entries)
    const magmaLUT = buildMagmaLUT();

    function buildMagmaLUT() {
      const stops = [
        [0.00, 0, 0, 4],
        [0.15, 30, 10, 60],
        [0.30, 80, 18, 105],
        [0.45, 140, 30, 110],
        [0.60, 195, 55, 85],
        [0.75, 235, 100, 50],
        [0.90, 252, 175, 45],
        [1.00, 252, 253, 140],
      ];
      const lut = new Array(256);
      for (let i = 0; i < 256; i++) {
        const t = i / 255;
        let lo = stops[0], hi = stops[stops.length - 1];
        for (let s = 0; s < stops.length - 1; s++) {
          if (t >= stops[s][0] && t <= stops[s + 1][0]) {
            lo = stops[s]; hi = stops[s + 1]; break;
          }
        }
        const f = (t - lo[0]) / (hi[0] - lo[0]);
        lut[i] = [
          Math.round(lo[1] + f * (hi[1] - lo[1])),
          Math.round(lo[2] + f * (hi[2] - lo[2])),
          Math.round(lo[3] + f * (hi[3] - lo[3])),
        ];
      }
      return lut;
    }

    function hzToMel(hz) { return 2595 * Math.log10(1 + hz / 700); }

    function buildMelBinMap(binCount, sampleRate, canvasHeight) {
      const nyquist = sampleRate / 2;
      const maxMel = hzToMel(nyquist);
      const map = new Int32Array(canvasHeight);
      for (let y = 0; y < canvasHeight; y++) {
        const melVal = (1 - y / canvasHeight) * maxMel;
        const hz = 700 * (Math.pow(10, melVal / 2595) - 1);
        const bin = Math.round((hz / nyquist) * binCount);
        map[y] = Math.max(0, Math.min(binCount - 1, bin));
      }
      return map;
    }

    function setMode(mel) {
      useMel = mel;
      btnMel.classList.toggle("active", mel);
      btnLinear.classList.toggle("active", !mel);
    }

    btnMel.addEventListener("click", () => setMode(true));
    btnLinear.addEventListener("click", () => setMode(false));

    function renderBirds(scores = new Map()) {
      const sorted = [...birds].sort((a, b) => (scores.get(b.id) || 0) - (scores.get(a.id) || 0));
      const topId = sorted[0]?.id;
      const top = sorted[0];

      if (running && top) {
        tipEl.textContent = top.tip;
      }

      birdList.innerHTML = sorted.map((bird) => {
        const pct = Math.round((scores.get(bird.id) || 0) * 100);
        const highlighted = bird.id === topId && running ? "highlight" : "";
        const score = running ? `${pct}%` : "";
        return `
          <div class="bird ${highlighted}">
            <div class="thumb">${bird.tag}</div>
            <div>
              <div class="name">${bird.common}</div>
              <div class="latin">${bird.latin}</div>
            </div>
            <div class="score">${score}</div>
          </div>
        `;
      }).join("");
    }

    function resizeCanvas() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.fillStyle = "#eee9df";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    function bandEnergy(data, sampleRate, lowHz, highHz) {
      const nyquist = sampleRate / 2;
      const start = Math.max(0, Math.floor((lowHz / nyquist) * data.length));
      const end = Math.min(data.length - 1, Math.ceil((highHz / nyquist) * data.length));
      let sum = 0;
      let count = 0;
      for (let i = start; i <= end; i++) {
        sum += data[i] / 255;
        count++;
      }
      return count ? sum / count : 0;
    }

    function updateClassifier(data) {
      const sr = audioContext.sampleRate;
      const low = bandEnergy(data, sr, 200, 900);
      const mid = bandEnergy(data, sr, 900, 2600);
      const high = bandEnergy(data, sr, 2600, 7000);
      const veryHigh = bandEnergy(data, sr, 7000, 11000);
      const wide = (low + mid + high) / 3;

      const raw = new Map([
        ["goose", low * 1.2],
        ["finch", mid * 1.05 + high * 0.25],
        ["wren", high * 1.1 + veryHigh * 0.45],
        ["steller", wide * 0.9 + low * 0.2],
        ["junco", high * 0.85 + mid * 0.35],
        ["sparrow", mid * 0.8 + high * 0.45]
      ]);

      const max = Math.max(...raw.values(), 0.001);
      for (const [key, value] of raw) {
        const normalized = Math.min(0.99, Math.max(0, value / max));
        const previous = scoreState.get(key) || 0;
        scoreState.set(key, previous * 0.85 + normalized * 0.15);
      }
    }

    function drawSpectrogram() {
      if (!running || !analyser) return;

      analyser.getByteFrequencyData(freqData);
      updateClassifier(freqData);

      const w = canvas.width;
      const h = canvas.height;
      const sliceW = Math.max(1, Math.floor((window.devicePixelRatio || 1) * 2));

      const imageData = ctx.getImageData(sliceW, 0, w - sliceW, h);
      ctx.putImageData(imageData, 0, 0);

      if (useMel && (!melBinMap || melBinMap.length !== h)) {
        melBinMap = buildMelBinMap(freqData.length, audioContext.sampleRate, h);
      }

      for (let y = 0; y < h; y++) {
        const bin = useMel
          ? melBinMap[y]
          : Math.max(0, Math.min(freqData.length - 1, Math.floor((1 - y / h) * freqData.length)));
        const value = freqData[bin];
        if (useMel) {
          const [r, g, b] = magmaLUT[value];
          ctx.fillStyle = `rgb(${r},${g},${b})`;
        } else {
          const warmth = value / 255;
          ctx.fillStyle = `rgb(${Math.floor(238 - value * 0.25)},${Math.floor(233 - value * 0.58)},${Math.floor(223 - value * 0.82 + warmth * 36)})`;
        }
        ctx.fillRect(w - sliceW, y, sliceW, 1);
      }

      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const ss = String(elapsed % 60).padStart(2, "0");
      timerEl.textContent = `${mm}:${ss}`;

      renderBirds(scoreState);
      raf = requestAnimationFrame(drawSpectrogram);
    }

    async function start() {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        statusEl.textContent = "Microphone requires HTTPS or localhost. In Chrome, visit chrome://flags/#unsafely-treat-insecure-origin-as-secure and add this origin.";
        return;
      }

      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false
        }
      });

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.05;
      freqData = new Uint8Array(analyser.frequencyBinCount);
      source.connect(analyser);

      scoreState = new Map(birds.map((bird) => [bird.id, 0]));
      running = true;
      startedAt = Date.now();
      button.classList.add("running");
      statusEl.textContent = `Listening at ${Math.round(audioContext.sampleRate / 1000)} kHz. Heuristic preview only.`;
      drawSpectrogram();
    }

    function stop() {
      running = false;
      button.classList.remove("running");
      if (raf) cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach((track) => track.stop());
      if (audioContext) audioContext.close();
      stream = null;
      audioContext = null;
      analyser = null;
      source = null;
      timerEl.textContent = "00:00";
      statusEl.textContent = "Stopped.";
      tipEl.textContent = "Press record and allow microphone access. This preview uses simple spectral heuristics, not a trained bird model.";
    }

    button.addEventListener("click", async () => {
      try {
        if (running) {
          stop();
        } else {
          await start();
        }
      } catch (err) {
        console.error(err);
        statusEl.textContent = err?.message || "Could not start microphone.";
      }
    });

    window.addEventListener("resize", () => { resizeCanvas(); melBinMap = null; });
    resizeCanvas();
    renderBirds(new Map([
      ["steller", 0.22],
      ["goose", 0.19],
      ["wren", 0.18],
      ["junco", 0.51],
      ["finch", 0.17],
      ["sparrow", 0.15]
    ]));
  </script>
</body>
</html>
"""

app = Bottle()


def prune_old_artifacts(max_age_seconds: int = 60 * 60 * 24) -> None:
    """Removes stale demo runs from /tmp so the app stays scrappy but bounded."""
    if not ARTIFACT_ROOT.exists():
        return

    cutoff = time.time() - max_age_seconds
    for child in ARTIFACT_ROOT.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child)
        except FileNotFoundError:
            continue


def make_run_dir(prefix: str) -> tuple[str, Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    prune_old_artifacts()
    run_id = f"{prefix}-{uuid.uuid4().hex[:10]}"
    run_dir = ARTIFACT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def write_run_state(
    run_dir: Path,
    *,
    result: dict[str, object],
    message: str,
    options: dict[str, str],
) -> None:
    state = {
        "result": result,
        "message": message,
        "options": options,
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def load_run_state(run_id: str) -> tuple[dict[str, object] | None, str, dict[str, str]]:
    state_path = ARTIFACT_ROOT / run_id / "state.json"
    if not state_path.exists():
        return None, DEFAULT_TEXT, dict(DEFAULT_OPTIONS)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    result = state.get("result")
    message = state.get("message", DEFAULT_TEXT)
    options = dict(DEFAULT_OPTIONS)
    options.update(state.get("options", {}))
    return result, message, options


def run_cli(
    command: list[str], *, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        input=input_bytes,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )


def make_bit_html(payload: bytes, *, limit: int = 96) -> str:
    bits = birdsong.bytes_to_bits(payload)[:limit]
    cells = []
    for bit in bits:
        cls = "bit one" if bit else "bit"
        cells.append(f'<span class="{cls}">{bit}</span>')
    if len(payload) * 8 > limit:
        cells.append('<span class="pill">…</span>')
    return "".join(cells)


def make_protocol_html(payload: bytes) -> str:
    """Render the full protocol structure: handshake + payload bytes + checksum."""
    checksum_val = birdsong.calculate_checksum(payload)
    parts = []

    # Handshake
    parts.append('<div class="byte-group">')
    parts.append('<div class="bits">')
    parts.append('<span class="bit handshake">H</span>')
    parts.append('<span class="bit handshake">H</span>')
    parts.append("</div>")
    parts.append('<span class="byte-label">handshake</span>')
    parts.append("</div>")

    # Payload bytes
    for b in payload:
        bits = [(b >> i) & 1 for i in range(7, -1, -1)]
        parts.append('<div class="byte-group">')
        parts.append('<div class="bits">')
        for bit in bits:
            cls = "bit one" if bit else "bit"
            parts.append(f'<span class="{cls}">{bit}</span>')
        parts.append("</div>")
        ch = chr(b) if 32 <= b < 127 else f"0x{b:02x}"
        parts.append(f'<span class="byte-label">{ch}</span>')
        parts.append("</div>")

    # Checksum byte
    checksum_bits = [(checksum_val >> i) & 1 for i in range(7, -1, -1)]
    parts.append('<div class="byte-group">')
    parts.append('<div class="bits">')
    for bit in checksum_bits:
        cls = "bit checksum one" if bit else "bit checksum"
        parts.append(f'<span class="{cls}">{bit}</span>')
    parts.append("</div>")
    parts.append(f'<span class="byte-label">chk 0x{checksum_val:02x}</span>')
    parts.append("</div>")

    return "".join(parts)


def format_text_preview(data: bytes) -> str:
    return data.decode("utf-8", errors="replace") if data else ""


def create_spectrogram(wav_path: Path, output_path: Path) -> None:
    sample_rate, samples = wavfile.read(wav_path)
    samples = birdsong.normalize_audio_samples(samples)

    frequencies, times, spectrum = signal.spectrogram(samples, sample_rate)
    log_spectrum = np.log1p(spectrum)

    plt.figure(figsize=(10, 4))
    plt.pcolormesh(times, frequencies, log_spectrum, shading="gouraud")
    plt.ylim(0, 5000)
    plt.ylabel("Frequency [Hz]")
    plt.xlabel("Time [s]")
    plt.title("Birdsong Spectrogram")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def wav_metadata(wav_path: Path) -> dict[str, str]:
    sample_rate, samples = wavfile.read(wav_path)
    sample_count = (
        len(samples) if getattr(samples, "ndim", 1) == 1 else samples.shape[0]
    )
    duration = sample_count / sample_rate
    return {
        "sample_rate": f"{sample_rate} Hz",
        "duration": f"{duration:.2f}s",
    }


def build_common_result(
    *,
    run_id: str,
    title: str,
    kind: str,
    summary: str,
    payload: bytes,
    wav_path: Path,
    spectrogram_path: Path,
    stderr: str,
    cli: str,
    decoded_text: str,
    ok: bool,
) -> dict[str, object]:
    metadata = wav_metadata(wav_path)
    metadata["byte_count"] = str(len(payload))
    return {
        "title": title,
        "kind": kind,
        "summary": summary,
        "decoded_text": decoded_text,
        "bit_html": make_bit_html(payload) if payload else "",
        "protocol_html": make_protocol_html(payload) if payload else "",
        "stderr": stderr.strip(),
        "ok": ok,
        "cli": cli,
        "audio_url": f"/artifacts/{run_id}/{wav_path.name}",
        "spectrogram_url": f"/artifacts/{run_id}/{spectrogram_path.name}",
        "metadata": metadata,
    }


def encode_result(
    message: str, options: dict[str, str], *, canned: bool = False
) -> tuple[dict[str, object], Path]:
    payload = message.encode("utf-8")
    run_id, run_dir = make_run_dir("encode")
    wav_path = run_dir / "encoded.wav"
    spectrogram_path = run_dir / "spectrogram.png"

    cli = [
        sys.executable,
        str(ROOT / "birdsong.py"),
        "send",
        "-o",
        str(wav_path),
        "--bit-duration",
        options["bit_duration"],
        "--freq0",
        options["freq0"],
        "--freq1",
        options["freq1"],
        "--freq-start",
        options["freq_start"],
    ]
    send = run_cli(cli, input_bytes=payload)
    if send.returncode != 0:
        return (
            build_error_result(
                title="Encoding failed",
                kind="Encode",
                summary="The CLI returned a non-zero exit code while generating audio.",
                stderr=send.stderr.decode("utf-8", errors="replace"),
                cli=format_cli_block(cli, stdin_hint="printf '%s' '...message...'"),
                payload=payload,
            ),
            run_dir,
        )

    decode_cli = [
        sys.executable,
        str(ROOT / "birdsong.py"),
        "recv",
        "-i",
        str(wav_path),
    ]
    decode = run_cli(decode_cli)
    create_spectrogram(wav_path, spectrogram_path)

    kind = "Canned demo" if canned else "Encode"
    summary = (
        "Generated a short transmission through the supported modem, decoded it again, "
        "and rendered the spectrogram."
        if canned
        else "Generated audio with the supported modem and immediately ran the decode path against it."
    )
    stderr = "\n".join(
        part
        for part in [
            send.stderr.decode("utf-8", errors="replace").strip(),
            decode.stderr.decode("utf-8", errors="replace").strip(),
        ]
        if part
    )
    return (
        build_common_result(
            run_id=run_id,
            title="Birdsong round-trip",
            kind=kind,
            summary=summary,
            payload=payload,
            wav_path=wav_path,
            spectrogram_path=spectrogram_path,
            stderr=stderr,
            cli=format_cli_block(cli, stdin_hint=f"printf '%s' {shlex.quote(message)}"),
            decoded_text=format_text_preview(decode.stdout),
            ok=decode.returncode == 0 and decode.stdout == payload,
        ),
        run_dir,
    )


def decode_result(
    upload_name: str, upload_bytes: bytes
) -> tuple[dict[str, object], Path]:
    run_id, run_dir = make_run_dir("decode")
    wav_path = run_dir / safe_name(upload_name)
    spectrogram_path = run_dir / "spectrogram.png"
    wav_path.write_bytes(upload_bytes)

    decode_cli = [
        sys.executable,
        str(ROOT / "birdsong.py"),
        "recv",
        "-i",
        str(wav_path),
    ]
    decode = run_cli(decode_cli)
    create_spectrogram(wav_path, spectrogram_path)
    decoded_bytes = decode.stdout

    return (
        build_common_result(
            run_id=run_id,
            title="Decoded uploaded WAV",
            kind="Decode",
            summary="Ran the uploaded WAV through the supported decoder and rendered the resulting spectrogram.",
            payload=decoded_bytes,
            wav_path=wav_path,
            spectrogram_path=spectrogram_path,
            stderr=decode.stderr.decode("utf-8", errors="replace"),
            cli=format_cli_block(decode_cli),
            decoded_text=format_text_preview(decoded_bytes),
            ok=decode.returncode == 0,
        ),
        run_dir,
    )


def safe_name(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return f"upload{suffix if suffix else '.wav'}"


def format_cli_block(command: list[str], *, stdin_hint: str | None = None) -> str:
    parts = [shlex.quote(part) for part in command]
    wrapped = []
    current = parts[0]

    for part in parts[1:]:
        if part.startswith("-") or len(current) > 72:
            wrapped.append(current)
            current = f"  {part}"
        else:
            current = f"{current} {part}"

    wrapped.append(current)
    command_block = " \\\n".join(wrapped)

    if stdin_hint is None:
        return command_block

    return f"{stdin_hint} | \\\n{command_block}"


def build_error_result(
    *,
    title: str,
    kind: str,
    summary: str,
    stderr: str = "",
    cli: str = "",
    payload: bytes = b"",
) -> dict[str, object]:
    return {
        "title": title,
        "kind": kind,
        "summary": summary,
        "decoded_text": format_text_preview(payload),
        "bit_html": make_bit_html(payload) if payload else "",
        "stderr": stderr.strip(),
        "ok": False,
        "cli": cli,
        "audio_url": "",
        "spectrogram_url": "",
        "metadata": {
            "byte_count": str(len(payload)),
            "duration": "-",
            "sample_rate": "-",
        },
    }


def render_page(
    *,
    result: dict[str, object] | None = None,
    message: str = DEFAULT_TEXT,
    options: dict[str, str] | None = None,
) -> str:
    merged_options = dict(DEFAULT_OPTIONS)
    if options:
        merged_options.update(options)
    response.content_type = "text/html; charset=utf-8"
    return template(
        PAGE_TEMPLATE,
        result=result,
        message=message,
        options=merged_options,
    )


@app.get("/")
def index() -> str:
    run_id = request.query.get("run", "").strip()
    if not run_id:
        return render_page()

    result, message, options = load_run_state(run_id)
    return render_page(result=result, message=message, options=options)


@app.get("/spectro-preview")
def spectro_preview() -> str:
    response.content_type = "text/html; charset=utf-8"
    return SPECTRO_PREVIEW_TEMPLATE


@app.post("/demo")
def canned_demo() -> str:
    try:
        result, run_dir = encode_result(
            DEFAULT_TEXT, dict(DEFAULT_OPTIONS), canned=True
        )
    except Exception as exc:  # pragma: no cover - defensive UI path
        _, run_dir = make_run_dir("error")
        result = build_error_result(
            title="Demo failed",
            kind="Canned demo",
            summary="The demo app hit an unexpected error while generating the canned transmission.",
            stderr=str(exc),
        )
    write_run_state(
        run_dir, result=result, message=DEFAULT_TEXT, options=dict(DEFAULT_OPTIONS)
    )
    redirect(f"/?run={run_dir.name}#result")


@app.post("/encode")
def encode() -> str:
    options = {
        "bit_duration": request.forms.get(
            "bit_duration", DEFAULT_OPTIONS["bit_duration"]
        ).strip(),
        "freq0": request.forms.get("freq0", DEFAULT_OPTIONS["freq0"]).strip(),
        "freq1": request.forms.get("freq1", DEFAULT_OPTIONS["freq1"]).strip(),
        "freq_start": request.forms.get(
            "freq_start", DEFAULT_OPTIONS["freq_start"]
        ).strip(),
    }
    message = request.forms.get("message", DEFAULT_TEXT)
    try:
        result, run_dir = encode_result(message, options)
    except Exception as exc:  # pragma: no cover - defensive UI path
        _, run_dir = make_run_dir("error")
        result = build_error_result(
            title="Encoding failed",
            kind="Encode",
            summary="The demo app hit an unexpected error while preparing artifacts.",
            stderr=str(exc),
            payload=message.encode("utf-8"),
        )
    write_run_state(run_dir, result=result, message=message, options=options)
    redirect(f"/?run={run_dir.name}#result")


@app.post("/decode")
def decode() -> str:
    upload = request.files.get("audio_file")
    if upload is None or not upload.filename:
        _, run_dir = make_run_dir("error")
        result = build_error_result(
            title="Decode failed",
            kind="Decode",
            summary="No WAV file was uploaded.",
            cli="Upload a WAV file first.",
        )
        write_run_state(
            run_dir, result=result, message=DEFAULT_TEXT, options=dict(DEFAULT_OPTIONS)
        )
        redirect(f"/?run={run_dir.name}#result")

    upload_bytes = upload.file.read()
    try:
        result, run_dir = decode_result(upload.filename, upload_bytes)
    except Exception as exc:  # pragma: no cover - defensive UI path
        _, run_dir = make_run_dir("error")
        result = build_error_result(
            title="Decode failed",
            kind="Decode",
            summary="The uploaded file could not be processed as a supported WAV artifact.",
            stderr=str(exc),
        )
    write_run_state(
        run_dir, result=result, message=DEFAULT_TEXT, options=dict(DEFAULT_OPTIONS)
    )
    redirect(f"/?run={run_dir.name}#result")


@app.get("/artifacts/<run_id>/<filename:path>")
def artifacts(run_id: str, filename: str):
    return static_file(filename, root=str(ARTIFACT_ROOT / run_id))


class SSLServer(bottle.ServerAdapter):
    """WSGIRefServer with TLS support via a self-signed cert."""

    def run(self, handler):
        import ssl
        from wsgiref.simple_server import make_server

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(self.options["certfile"], self.options["keyfile"])
        srv = make_server(self.host, self.port, handler)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        srv.serve_forever()


def ensure_self_signed_cert() -> tuple[str, str]:
    cert_dir = ARTIFACT_ROOT / "ssl"
    cert_dir.mkdir(parents=True, exist_ok=True)
    certfile = cert_dir / "cert.pem"
    keyfile = cert_dir / "key.pem"
    if certfile.exists() and keyfile.exists():
        return str(certfile), str(keyfile)

    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(keyfile), "-out", str(certfile),
            "-days", "365", "-nodes",
            "-subj", "/CN=birdsong-demo",
        ],
        check=True,
        capture_output=True,
    )
    return str(certfile), str(keyfile)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Birdsong demo server")
    parser.add_argument(
        "--host",
        default=os.environ.get("BIRDSONG_DEMO_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("BIRDSONG_DEMO_PORT", "8333")),
    )
    parser.add_argument("--ssl", action="store_true", help="Serve over HTTPS with a self-signed cert")
    args = parser.parse_args()

    if args.ssl:
        certfile, keyfile = ensure_self_signed_cert()
        print(f"Birdsong demo on https://{args.host}:{args.port}")
        app.run(
            host=args.host, port=args.port,
            server=SSLServer, certfile=certfile, keyfile=keyfile,
            debug=False, reloader=False,
        )
    else:
        print(f"Birdsong demo on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=False, reloader=False)


if __name__ == "__main__":
    main()
