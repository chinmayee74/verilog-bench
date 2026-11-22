import re, subprocess, time, os, tempfile
import streamlit as st
from google import genai
import vcdvcd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODEL = "gemini-3.5-flash-lite"
MAX_TRIES = 5

st.set_page_config(page_title="Verilog Bench | Chinmayee K", page_icon="⚡")

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 2.5rem; max-width: 820px;}
.title {font-size: 2.3rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 0;}
.sub {font-size: 1.05rem; color: #52606D; margin: 0.2rem 0 1rem 0;}
.byline {font-size: 0.9rem; color: #1F3A5F; font-weight: 600;
         border-left: 3px solid #1F3A5F; padding-left: 10px; margin-bottom: 1.5rem;}
</style>
<div class="title">Verilog Bench</div>
<div class="sub">Describe a digital circuit. Get the Verilog, a testbench, a simulation result and a waveform.</div>
<div class="byline">Built by Chinmayee K &nbsp;|&nbsp; ECE, 3rd Semester, NIE Mysuru<br>
Digital Electronics: AI-integrated experiential learning project</div>
""", unsafe_allow_html=True)

# access code so only people who have it can use your Gemini quota
pw = st.text_input("Access code", type="password")
if pw != st.secrets["APP_PASSWORD"]:
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

RULES = """DESIGN RULES:
- Beginner friendly: simple Verilog-2001 only, clear signal names, and a short comment on every block in plain English.
- Optimized: minimum logic and registers, no unused signals, no accidental latches, synthesizable.
- Header comment at the top: module name, inputs, outputs, what it does.

TESTBENCH RULES:
- Module named tb. Include: initial begin $dumpfile("wave.vcd"); $dumpvars(0, tb); end
- Test ALL input combinations only if the total number of input bits is 6 or fewer. Otherwise test 15 to 20 chosen cases (all zeros, all ones, carry, overflow, a few random values), and test every operation or select value at least twice.
- Never print more than 25 lines of test output.
- For clocked circuits, change inputs at negedge clk.
- If there are several implementations, check they all match.
- Print one line per test with inputs, actual output, expected output and PASS or FAIL.
- Print FAIL for any wrong result.
- At the end print: Summary: X tests run, Y passed
- Print ALL TESTS PASSED only if every test is correct, then call $finish.
Use plain Verilog-2001 that works in Icarus Verilog."""

EXPLAIN = """After the two code blocks, write a plain-text explanation starting with EXPLANATION: in at most 6 short lines, simple English for a 3rd semester ECE student: what the circuit does, how the code works, what the testbench covers, and one limitation."""


def ask(prompt):
    for _ in range(5):
        try:
            return client.models.generate_content(model=MODEL, contents=prompt).text
        except Exception:
            time.sleep(8)
    return None


def get_code(text):
    blocks = re.findall(r"```(?:verilog|systemverilog|v)?\n(.*?)```", text, re.S)
    return blocks[0], blocks[1]


def get_explanation(text):
    return text.rsplit("```", 1)[-1].strip()


def run_sim(design, tb):
    d = tempfile.mkdtemp()
    open(os.path.join(d, "design.v"), "w").write(design)
    open(os.path.join(d, "tb.v"), "w").write(tb)
    c = subprocess.run(["iverilog", "-o", "sim", "tb.v", "design.v"],
                       capture_output=True, text=True, cwd=d)
    if c.returncode != 0:
        return False, c.stderr, None
    r = subprocess.run(["vvp", "sim"], capture_output=True, text=True, cwd=d, timeout=30)
    out = r.stdout + r.stderr
    vcd = os.path.join(d, "wave.vcd")
    ok = "ALL TESTS PASSED" in out and "FAIL" not in out
    return ok, out, (vcd if os.path.exists(vcd) else None)


def draw_wave(path):
    v = vcdvcd.VCDVCD(path, store_tvs=True)
    skip = ("i_", "tests_", "test_", "total_", "pass", "fail", "error", "count", "idx", "loop")
    names = [n for n in v.signals
             if n.count(".") == 1 and not n.split(".")[-1].lower().startswith(skip)][:12]
    if not names:
        names = list(v.signals)[:12]
    end = max(int(v.endtime), 1)
    fig, axes = plt.subplots(len(names), 1, figsize=(10, len(names) * 0.9 + 1), sharex=True)
    if len(names) == 1:
        axes = [axes]
    for ax, n in zip(axes, names):
        tv = v[n].tv
        if not tv:
            continue
        times = [int(t) for t, _ in tv] + [end]
        vals = []
        for _, x in tv:
            try:
                vals.append(int(x, 2))
            except ValueError:
                vals.append(0)
        ax.step(times, vals + [vals[-1]], where="post", color="#1F3A5F")
        ax.margins(y=0.5)
        if len(tv) <= 30 and int(v[n].size) > 1:
            for i, (t, x) in enumerate(tv):
                mid = (times[i] + times[i + 1]) / 2
                ax.text(mid, vals[i], x, fontsize=8, ha="center", va="bottom")
        ax.set_yticks([])
        ax.set_ylabel(n.split(".")[-1], rotation=0, ha="right", va="center")
    axes[-1].set_xlabel("time")
    fig.tight_layout()
    return fig


def short_log(log, n=12):
    lines = log.strip().splitlines()
    if len(lines) <= n + 4:
        return log
    hidden = len(lines) - n - 3
    return "\n".join(lines[:n] + [f"... {hidden} more lines hidden ..."] + lines[-3:])


spec = st.text_area("Circuit description",
                    placeholder="4-bit ALU with add, subtract, AND, OR... Print all values in binary")

if st.button("Generate and test") and spec.strip():
    prompt = f"""Write Verilog for this circuit: {spec}
If the description is not a digital circuit, reply with only the word INVALID.
Otherwise reply with exactly this, in order:
1) a code block with the design module
2) a code block with a self-checking testbench
3) the explanation
{RULES}
{EXPLAIN}"""
    for attempt in range(1, MAX_TRIES + 1):
        st.subheader(f"Attempt {attempt}")
        with st.spinner("AI is writing the code..."):
            reply = ask(prompt)
        if reply is None:
            st.error("Gemini is busy. Try again in a minute.")
            break
        if reply.strip().startswith("INVALID"):
            st.warning("Please describe a digital circuit, like a counter, ALU or FSM.")
            break
        try:
            design, tb = get_code(reply)
        except Exception:
            st.warning("AI reply format was wrong, retrying...")
            continue
        ok, log, vcd_path = run_sim(design, tb)
        st.code(short_log(log))
        with st.expander("Full simulator output"):
            st.code(log)
        if ok:
            st.success(f"PASSED in {attempt} attempt(s)")
            st.markdown("**Explanation**")
            st.write(get_explanation(reply))
            if vcd_path:
                st.markdown("**Waveform**")
                try:
                    st.pyplot(draw_wave(vcd_path))
                except Exception as e:
                    st.warning(f"Could not draw the waveform: {e}")
                st.download_button("Download wave.vcd", open(vcd_path).read(), "wave.vcd")
            with st.expander("Design code (design.v)", expanded=True):
                st.code(design, language="verilog")
            with st.expander("Testbench (tb.v)"):
                st.code(tb, language="verilog")
            break
        st.error("FAILED, sending the error back to the AI to fix...")
        prompt = f"""Spec: {spec}
Your previous design:
```verilog
{design}
```
Testbench:
```verilog
{tb}
```
Icarus output:
{log}
Fix the problem. Reply with exactly: corrected design code block, corrected testbench code block, then the explanation.
{RULES}
{EXPLAIN}"""
    else:
        st.error(f"Did not pass in {MAX_TRIES} attempts")

st.markdown("---")
st.caption("Chinmayee K, ECE, NIE Mysuru. Code is generated by an LLM and checked with Icarus Verilog.")
