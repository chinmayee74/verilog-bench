# Verilog Bench

A tool that turns a plain-English circuit description into Verilog code and a testbench using an LLM (Gemini), then simulates it with Icarus Verilog. If the simulation fails, the error is sent back to the AI to fix, up to 5 attempts. It shows the test table, explanation and waveform.

Built by Chinmayee K, ECE (3rd Semester), NIE Mysuru
Digital Electronics: AI-integrated experiential learning project

Tools: Python, Streamlit, Gemini API, Icarus Verilog
