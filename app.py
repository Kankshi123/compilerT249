from flask import Flask, request, jsonify, render_template_string
from lark import Lark, Transformer, UnexpectedInput

app = Flask(__name__)

python_grammar = r"""
start: stmt*

stmt: print_stmt
    | assign_stmt
    | if_stmt
    | input_stmt

print_stmt: "print" "(" expr ")" ";"
assign_stmt: "int" NAME "=" expr ";"
input_stmt: NAME "=" "input" "(" STRING ")" ";"
if_stmt: "if" "(" condition ")"  "{" stmt* "}"

?expr: STRING           -> string
     | NUMBER          -> number
     | NAME            -> var
     | expr "+" expr   -> add
     | expr "-" expr   -> sub
     | expr "*" expr   -> mul
     | expr "/" expr   -> div
     | "(" expr ")"

condition: expr "==" expr

NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
STRING: /"[^"]*"/
NUMBER: /\d+/

%import common.WS
%ignore WS
"""

KEYWORD_TYPO_MAP = {
    'pritn': 'print',
    'improt': 'import',
    'functoin': 'function',
    'retun': 'return',
    'brak': 'break',
    'contnue': 'continue',
    'els': 'else',
    'defualt': 'default',
    'swich': 'switch',
    'whlie': 'while',
}

class TypoCorrector(Transformer):
    def NAME(self, token):
        value = str(token)
        if value in KEYWORD_TYPO_MAP:
            suggestion = KEYWORD_TYPO_MAP[value]
            print(f"❌ Typo Detected in parse: '{value}' → Suggested Correction: '{suggestion}'")
            token.value = suggestion
        return token

parser = Lark(python_grammar, parser='lalr', transformer=TypoCorrector())

def preprocess_typos(code):
    import re
    for typo, correction in KEYWORD_TYPO_MAP.items():
        pattern = r'\b' + re.escape(typo) + r'\b'
        code = re.sub(pattern, correction, code)
    return code

def detect_errors(code):
    errors = []
    if code.count("{") != code.count("}"):
        errors.append("Unbalanced braces detected.")
    if code.count("(") != code.count(")"):
        errors.append("Unbalanced parentheses detected.")
    if code.count('"') % 2 != 0:
        errors.append("Unbalanced double quotes detected.")
    return errors

def correct_code(code):
    import re
    code = preprocess_typos(code)
    lines = code.split('\n')
    corrected_lines = []

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            corrected_lines.append(line)
            continue

        open_par = line.count('(')
        close_par = line.count(')')
        close_needed = open_par - close_par if open_par > close_par else 0

        quote_count = line.count('"')
        quote_needed = 1 if quote_count % 2 != 0 else 0

        ends_semicolon = line_strip.endswith(';')
        line_core = line.rstrip(';')

        if close_needed > 0:
            line_core += ')' * close_needed

        if quote_needed:
            if close_needed > 0:
                insert_pos = len(line_core) - close_needed
                line_core = line_core[:insert_pos] + '"' + line_core[insert_pos:]
            else:
                line_core += '"'

        if not ends_semicolon and not line_core.endswith('{') and not line_core.endswith('}') and not line_strip.startswith(('if', 'else')):
            line_core += ';'

        corrected_lines.append(line_core)

    open_braces = code.count('{')
    close_braces = code.count('}')
    if open_braces > close_braces:
        corrected_lines.append('}' * (open_braces - close_braces))

    return '\n'.join(corrected_lines)

def analyze_code(code, auto_correct=False):
    # Preprocess typos before analysis
    preprocessed_code = preprocess_typos(code)
    if auto_correct:
        corrected_code = correct_code(preprocessed_code)
    else:
        corrected_code = preprocessed_code
    errors = detect_errors(code)
    error_details = []
    if errors:
        error_details.extend(errors)
    try:
        parser.parse(corrected_code)
    except UnexpectedInput as e:
        error_details.append(str(e))
    if error_details:
        # Return input code with errors plus suggestions and corrected code
        return {
            "status": "error",
            "details": error_details,
            "input_code": code,
            "suggested_correction": corrected_code
        }
    else:
        return {
            "status": "success",
            "input_code": code,
            "suggested_correction": corrected_code
        }

@app.route('/')
def index():
    return render_template_string(r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Custom Language Interpreter</title>
<style>
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #f0f2f5;
    margin: 0; padding: 20px;
    color: #333;
    display: flex; flex-direction: column;
    align-items: center;
    min-height: 100vh;
  }
  h1 {
    margin-bottom: 1rem;
    color: #222;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
  }
  #codeInput {
    width: 90vw;
    max-width: 800px;
    height: 250px;
    font-family: 'Source Code Pro', monospace;
    font-size: 1rem;
    padding: 12px;
    border-radius: 8px;
    border: 2px solid #4a90e2;
    background: #ffffff;
    box-shadow: 0 2px 6px rgba(74,144,226,0.2);
    resize: vertical;
    transition: border-color 0.3s ease;
    outline: none;
  }
  #codeInput:focus {
    border-color: #357ABD;
    box-shadow: 0 4px 10px rgba(53,122,189,0.4);
  }
  button {
    margin-top: 15px;
    padding: 10px 30px;
    font-size: 1.1rem;
    background-color: #4a90e2;
    color: #fff;
    border: none;
    border-radius: 8px;
    box-shadow: 0 4px 8px rgba(74,144,226,0.4);
    cursor: pointer;
    transition: background-color 0.3s ease;
  }
  button:hover {
    background-color: #357abd;
  }
  #output {
    margin-top: 25px;
    width: 90vw;
    max-width: 800px;
    min-height: 150px;
    background: #f9fafb;
    color: #222;
    border-radius: 8px;
    padding: 15px;
    white-space: pre-wrap;
    font-family: 'Source Code Pro', monospace;
    font-size: 0.95rem;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.05);
    user-select: text;
    border: 1px solid #ccc;
  }
  #output.error {
    color: #c00;
  }
  #labelInput, #labelSuggestion, #labelCorrected {
    font-weight: bold;
    margin-top: 15px;
  }
  pre.code-block {
    background: #eef2f7;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #ccd0d9;
    overflow-x: auto;
  }
</style>
</head>
<body>
  <h1>Custom Language Interpreter</h1>
  <label id="labelInput" for="codeInput">Input Code:</label>
  <textarea id="codeInput" aria-label="Code input">// Write your code here
// Example:
// pritn("Hello World")
// int x = 10
// if (x == 10) {
//    pritn("x is 10")
// }
  </textarea><br />
  <button onclick="runCode()">Run</button>
  <div id="output" class="error" style="display:none;">
    <div id="errorDetails"></div>
    <div id="suggestionSection" style="display:none;">
      <div id="labelSuggestion">Suggested Correction:</div>
      <pre id="suggestionCode" class="code-block"></pre>
      <div id="labelCorrected">Corrected Code:</div>
      <pre id="correctedCode" class="code-block"></pre>
    </div>
  </div>
<script>
async function runCode() {
  const code = document.getElementById("codeInput").value;
  const res = await fetch("/run", {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code })
  });
  const data = await res.json();
  const output = document.getElementById("output");
  const errorDetails = document.getElementById("errorDetails");
  const suggestionSection = document.getElementById("suggestionSection");
  const suggestionCode = document.getElementById("suggestionCode");
  const correctedCode = document.getElementById("correctedCode");

  if (data.status === "error") {
    output.style.display = "block";
    output.classList.add("error");
    errorDetails.textContent = "Errors found in input code:\n" + data.details.join("\n");
    suggestionCode.textContent = data.suggested_correction || "";
    correctedCode.textContent = data.corrected || "";
    suggestionSection.style.display = "block";
  } else {
    output.style.display = "block";
    output.classList.remove("error");
    errorDetails.textContent = "No errors found. Code is valid.";
    suggestionSection.style.display = "block";
    suggestionCode.textContent = data.suggested_correction || "";
    correctedCode.textContent = data.corrected || "";
  }
}
</script>
</body>
</html>
""")

@app.route('/run', methods=['POST'])
def run_code():
    code = request.json.get('code', '')
    try:
        response = analyze_code(code, auto_correct=True)
        return jsonify(response)
    except Exception as e:
        return jsonify({"status":"error", "details":[str(e)], "input_code": code, "suggested_correction": code})

if __name__ == '__main__':
    app.run(debug=True)

