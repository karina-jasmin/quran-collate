# Quran Manuscript Collation – Transformation Scripts & Data
## About This Repository

This repository contains Python scripts and datasets developed as part of a study on the automatic collation of early Quranic manuscripts. The research explores the challenges of transcribing and encoding Arabic script for computational text comparison, particularly focusing on rasm (consonantal skeleton), diacritical marks (iʿjām), and vowel markers (tashkīl).

One of the key tasks in this study was transforming manuscript transcriptions—specifically those from [Corpus Coranicum](https://corpuscoranicum.org)—to adapt them for different collation approaches. These approaches include:

1. Plain Text – Normalizing the transcriptions to retain only archigraphemic forms, removing diacritics and vocalization to enable baseline textual comparison.
2. XML-Based Encoding – Structuring transcriptions in TEI-compliant XML, preserving both base characters and diacritics as separate elements for more detailed analysis.

## Contents

This repository includes the following components:
1. Python Script for transforming [Corpus Coranicum transcriptions](https://github.com/telota/corpus-coranicum-xml-raw-files) (./CC-Transformer)
- cc_transformer.py – A script that extracts and transforms Corpus Coranicum transcriptions, normalizing characters and structuring them for different collation methods.
- Normalization & Encoding Data (./CC-Transformer/data)

2. Sample Transformed Transcriptions (./examples): Examples of transformed Quranic manuscript transcriptions in both plain text and TEI XML.

## Usage

To transform Corpus Coranicum transcriptions, use the provided script:

1. Clone this repository and install required packages into a virtual environment:

- `git clone https://github.com/karina-jasmin/quran-collate.git`
- `cd quran-collate`
- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`

2. Run the transformation script:

`py cc_transformer.py <cc_transcription> <output_file> <mode>`

- `<cc_transcription>`: Path to the Corpus Coranicum transcription file.
- `<output_file>` (optional): Path to save the transformed file. If no path is provided, the script automatically generates a name based on the input filename.
- `<mode>`: The transformation type, either:
  - `"full_trans"` – Converts the transcription into a structured XML/TEI model, preserving rasm, diacritics, and vowels.
  - `"plain_trans"` – Converts the transcription into plain text with normalized archigraphemes, suitable for simpler collation tasks.
