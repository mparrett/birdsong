That's a great question, and it's smart to think ahead about dependencies.

For the MVP as defined in the spec (simple FSK, reading from `stdin`, writing to `stdout`), **we will not need `scipy`**.

* The sender (`sendit.py`) can use Python's built-in `wave` module to write the `.wav` file, removing the need for `scipy`.
* The receiver (`recvit.py`) will also use the `wave` module to read the file for testing.
* The core signal processing function, the Fast Fourier Transform (FFT), is provided by `numpy`, which is a core dependency we're keeping.

However, you are right to be curious about its future use. If we were to implement the more advanced "bird song" spectrogram idea (Phase 3), the `scipy.signal` package would become extremely useful. It has powerful, pre-built functions for creating spectrograms and designing filters that would save a lot of time and effort.

**My recommendation:** Let's **remove `scipy` for now** and use the built-in `wave` module to keep the MVP as lean as possible. This stays true to the "few dependencies" goal. If and when we decide to build the more complex v2.0, we can add `scipy` back in, knowing that the added complexity justifies the new dependency.

uv run python3 sing.py

afplay poc_signal.wav

