"""Readable plain notation for common STEM math; unsupported TeX remains intact."""
import re

SYMBOLS = {
    "alpha":"α", "beta":"β", "gamma":"γ", "delta":"δ", "Delta":"Δ",
    "epsilon":"ε", "theta":"θ", "lambda":"λ", "mu":"μ", "pi":"π",
    "rho":"ρ", "sigma":"σ", "tau":"τ", "phi":"φ", "omega":"ω", "Omega":"Ω",
    "times":"×", "cdot":"·", "approx":"≈", "leq":"≤", "geq":"≥",
    "neq":"≠", "infty":"∞", "pm":"±", "rightarrow":"→", "parallel":"∥",
}
SUPER = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

def group(text, start):
    if start >= len(text) or text[start] != "{":
        raise ValueError()
    depth = 1
    for i in range(start+1, len(text)):
        depth += (text[i] == "{") - (text[i] == "}")
        if depth == 0:
            return text[start+1:i], i+1
    raise ValueError()

def plain_math(source, depth=0):
    if depth > 12:
        return source
    text=source.strip().replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    remaining=64
    try:
        while r"\frac" in text:
            remaining-=1
            if not remaining:
                return source
            start=text.index(r"\frac")
            a,end=group(text,start+5)
            b,end=group(text,end)
            a,b=plain_math(a,depth+1),plain_math(b,depth+1)
            if r"\frac" in a or r"\frac" in b:
                return source
            text=text[:start]+"("+a+")/("+b+")"+text[end:]
    except ValueError:
        return source
    text=re.sub(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}", r"\1", text)
    text=re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", text)
    text=re.sub(r"\\(?:left|right)(?=[()[\]|])", "", text)
    text=re.sub(r"\\([A-Za-z]+)", lambda m: SYMBOLS.get(m[1],m[0]), text)
    if re.search(r"\\[A-Za-z]+", text):
        return source
    text=re.sub(r"\^\{([0-9+\-]+)\}|\^([0-9])",
                lambda m: (m[1] or m[2]).translate(SUPER), text)
    text=re.sub(r"([_^])\{([^{}]+)\}", lambda m: m[1]+(m[2] if len(m[2])==1 else "("+m[2]+")"),text)
    text=text.replace(r"\,", " ").replace(r"\;", " ").replace(r"\!", "")
    return text

def readable_markdown(text):
    pattern = r"\\\[(.*?)\\\]|\\\((.*?)\\\)|\$\$(.*?)\$\$|(?<!\\)\$([^$\n]+)\$"
    def render(match):
        value=plain_math(next(g for g in match.groups() if g is not None)).replace(chr(96),"'")
        if match.group(1) is not None or match.group(3) is not None:
            return "\n\n    "+value.replace("\n","\n    ")+"\n\n"
        return " "+chr(96)+value+chr(96)+" "
    return re.sub(pattern,render,text,flags=re.DOTALL)
