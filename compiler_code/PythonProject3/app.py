from flask import Flask, request, jsonify, render_template
from lark import Lark, Transformer, UnexpectedInput

app = Flask(__name__)

# Initial typo dictionary
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

# Grammar with support for nested statements
python_grammar = r"""
start: stmt*

stmt: print_stmt
    | assign_stmt
    | if_stmt
    | input_stmt
    | loop_stmt

print_stmt: "print" "(" expr ")" ";"
assign_stmt: "int" NAME "=" expr ";"
input_stmt: NAME "=" "input" "(" STRING ")" ";"
if_stmt: "if" "(" condition ")" "{" stmt* "}"
loop_stmt: "while" "(" condition ")" "{" stmt* "}"

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

class TypoCorrector(Transformer):
    def NAME(self, token):
        value = str(token)
        if value in KEYWORD_TYPO_MAP:
            suggestion = KEYWORD_TYPO_MAP[value]
            print(f" Typo Detected in parse: '{value}' → Suggested Correction: '{suggestion}'")
            token.value = suggestion
        return token

# LALR parser for main parsing
parser = Lark(python_grammar, parser='lalr')

# EARLEY parser with placeholders for partial parse tree fallback
earley_parser = Lark(python_grammar, parser='earley', maybe_placeholders=True)

def preprocess_typos(code):
    import re
    for typo, correction in KEYWORD_TYPO_MAP.items():
        pattern = r'(?<!\w)' + re.escape(typo) + r'(?=\W|$)'

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
    lines = code.split('\\n')
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

        if not ends_semicolon and not line_core.endswith('{') and not line_core.endswith('}') and not line_strip.startswith(('if', 'else', 'while')):
            line_core += ';'

        corrected_lines.append(line_core)

    open_braces = code.count('{')
    close_braces = code.count('}')
    if open_braces > close_braces:
        corrected_lines.append('}' * (open_braces - close_braces))

    return '\\n'.join(corrected_lines)

def analyze_code(code, auto_correct=False):
    preprocessed_code = preprocess_typos(code)
    if auto_correct:
        corrected_code = correct_code(preprocessed_code)
    else:
        corrected_code = preprocessed_code
    errors = detect_errors(code)
    error_details = []
    parse_tree_str = None

    if errors:
        error_details.extend(errors)

    try:
        # Try main parsing with LALR parser
        tree = parser.parse(corrected_code)
        parse_tree_str = tree.pretty()
    except UnexpectedInput as e:
        error_details.append(str(e))
        # On parse error, try to get partial parse tree with EARLEY parser
        try:
            partial_tree = earley_parser.parse(corrected_code)
            parse_tree_str = partial_tree.pretty()
        except Exception:
            parse_tree_str = None

    if error_details:
        return {
            "status": "error",
            "details": error_details,
            "input_code": code,
            "suggested_correction": corrected_code,
            "parse_tree": parse_tree_str
        }
    else:
        return {
            "status": "success",
            "input_code": code,
            "suggested_correction": corrected_code,
            "parse_tree": parse_tree_str
        }

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/run', methods=['POST'])
def run_code():
    code = request.json.get('code', '')
    try:
        response = analyze_code(code, auto_correct=True)
        return jsonify(response)
    except Exception as e:
        return jsonify({"status":"error", "details":[str(e)], "input_code": code, "suggested_correction": code, "parse_tree": None})

@app.route('/add_typo', methods=['POST'])
def add_typo():
    data = request.json
    typo = data.get('typo')
    correction = data.get('correction')
    if typo and correction:
        KEYWORD_TYPO_MAP[typo] = correction
        return jsonify({"status": "success", "message": f"Added typo '{typo}' with correction '{correction}'."})
    return jsonify({"status": "error", "message": "Invalid input."})

if __name__ == '__main__':
    app.run(debug=True)
