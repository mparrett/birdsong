# Acoustic Modem Coursework 

Design, implement, and demo a **single‑file, robust, high‑throughput acoustic modem** written in Python. The project is intentionally constrained so you focus on the _interesting_ DSP and protocol ideas rather than plumbing. The goal is to create a working modem that can transmit and receive data over audio channels, such as laptop speakers and microphones. We will prioritize reliability but are aiming for innovative solutions to scale up throughput.

---

## 0 🔍 Quick Demo (What Success Looks Like)

```bash
# Phase 1 – loop‑back via disk
$ python3 modem.py send -o out.wav -m "Hello world!"
$ python3 modem.py recv -i out.wav
Hello world!

# Phase 2 – over‑the‑air between two laptops
(A)  $ python3 modem.py send -o tx.wav -m "Hello world, air‑gapped!"
$ afplay tx.wav           # or sox tx.wav -d

(B)  $ rec -c1 -b16 trim 0 4 rx.wav   # record ~4 s
$ python3 modem.py recv -i rx.wav
Hello world, air‑gapped!
```

---

## 1 🚧 Project Constraints

| Requirement                               | Notes                                                                                                                                                                                                              |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Single entry‑point file**               | Everything lives in `modem.py`. You may define as many helper classes / functions _inside_ it as you like.                                                                                                         |
| **Permitted libraries**                   | `numpy`, `scipy`, `soundfile` _or_ `wave`, `argparse`, `itertools`, `struct`, and the standard library. `matplotlib` is allowed **for debug/visualisation only** (plots must not run during normal CLI operation). |
| **< 800 logical LOC**                     | Measured by `cloc --exclude-lang=Markdown`, excluding empty lines and comments.                                                                                                                                    |
| **Must run on macOS ≥ 12, Python ≥ 3.10** | We will test on macOS laptops with built‑in mic / speakers.                                                                                                                                                        |

> **Why these limits?** A tight envelope forces creative but _readable_ solutions and ensures everyone fights the same battles.

---

## 2 📡 Reference Physical‑Layer Parameters (Recommended Start)

| Parameter       | Value                            | Rationale                                                                          |
| --------------- | -------------------------------- | ---------------------------------------------------------------------------------- |
| Sample rate     | **48 kHz**                       | Universal on laptops; aligns nicely with 1024‑pt FFT windows                       |
| FFT size / hop  | 1024‑sample Hann, 50 % overlap   | ≈ 21 ms frame, plenty of frequency resolution                                      |
| Symbol duration | **2 hops ≈ 40 ms**               | 25 baud → \~ 200 bps with 8 parallel carriers                                      |
| Carrier set     | **1 kHz + n·375 Hz** (n = 0 … 7) | Forms a stack of G–C perfect‑fourth harmonics; remains in laptop speaker pass‑band |

Feel free to deviate _after_ you have a working baseline.

---

## 3 📜 Suggested Frame Format (Framed Protocol)

```
┌──────────┬──────────┬─────────────┬───────────┐
│ Preamble │  Header  │  Payload    │  Checksum │
└──────────┴──────────┴─────────────┴───────────┘
```

- **Preamble** – a unique 2‑D bitmap pattern used for coarse sync and auto‑gain.
- **Header (fixed 4 bytes)** – payload length (2 B) + 2 B CRC‑16.
- **Payload** – raw user data.
- **Checksum** – CRC‑16 of the _payload_ (duplicate of header CRC is OK).

### Optional Forward‑Error‑Correction (Extra Credit)

Implement block interleaving + Hamming(12,8) or Reed–Solomon before checksum.

---

## 4 🛠️ Implementation Tips

1. **Bitmap mindset** – treat the time‑frequency spectrogram like an image: write bits, then iFFT each column to emit audio. This is not the ONLY approach you should consider, but it is a strong paradigm.
2. **2‑D correlation for sync** – slide a template of the preamble over the spectrogram to locate frame 0.
3. **Adaptive thresholding** – estimate noise floor during silent rows in the preamble, then normalise magnitude bins.
4. **Iterate > optimise** – a naïve, readable slicer that works in quiet loop‑back beats an abandoned ML classifier.
5. **Draw inspiration from research and biology** - Ask professor for relevant papers if you don't know of any.

---

## 5 📁 Artifact Structure

All your files will be stored under your team's directory, e.g. `team_1`.

The layout is as follows:

```
team_1/
├── modem.py          - your single file implementation
├── wav/              - generated wav files
├── png/              - spectrograms, plots, etc.
├── justfile          - justfile (recommended)
└── pyproject.toml    - project file (uv recommended, it will create this)
```

---

## 6 🎯 Stretch‑Goal Menu (Pick Any Two)

| Title                 | One‑liner                                        |                              |
| --------------------- | ------------------------------------------------ | ---------------------------- |
| Auto‑gain control     | Learn RMS in preamble, scale bins accordingly    |                              |
| Live streaming        | Pipe audio via \`sox …                           | python3 modem.py recv -i -\` |
| Spectrogram watermark | Encode melody / logo in phase or intensity       |                              |
| Real‑time spectrum UI | Think `curses` waterfall for debugging |                              |
| Bio-inspired approach | Birdsong? Insects? Whales? Human vocal properties|   |  

---

## 7 📑 Grading Rubric (100 pts)

| Criterion                                           | Pts |
| --------------------------------------------------- | --- |
| **Phase 1 CLI** works exactly as spec               | 40  |
| Decodes ≥ 30 B loop‑back payload with < 1 bit error | 20  |
| All provided unit tests pass                        | 15  |
| Code quality (≤ 800 LOC, docstrings, PEP‑8)         | 10  |
| Two stretch goals                                   | 15  |

We will explore Phase 2 in a separate project.

---

## 8 🎶 Why G–C Perfect‑Fourth Harmony?

Two tones a perfect fourth apart yield closely spaced harmonics that sum _consonantly_, reducing inter‑modulation products that would otherwise muddy laptop speakers. You get a signal that’s gentler on human ears **and** on crude hardware. You are not strictly bound to this idea, but it is a STRONG suggestion.

---

## 9 📜 Appendix — Handy macOS Commands

These tools are likely already installed on your systems. If not, please install. They are highly recomended and will help you with your project.

````bash
brew install uv
uv add ...
uv run ...
```

```bash
# Install just for creating fast recipes
brew install just
just test
```

```bash
# Install sox (if needed)
brew install sox

# Record 4 seconds mono, 16‑bit PCM
rec -c1 -b16 trim 0 4 out.wav

# Play a file
afplay out.wav   # or sox out.wav -d
```

