

def doc_text(doc) -> str:
    # string direto
    if isinstance(doc, str):
        return doc

    # tenta atributos comuns
    for attr in ("text", "content", "page_content", "pageContent"):
        val = getattr(doc, attr, None)
        if isinstance(val, str) and val.strip():
            return val

    # tenta como dict
    if isinstance(doc, dict):
        for k in ("text", "content", "page_content", "pageContent"):
            if isinstance(doc.get(k), str) and doc[k].strip():
                return doc[k]

    # tenta to_dict()/dict()
    for m in ("to_dict", "dict"):
        fn = getattr(doc, m, None)
        if callable(fn):
            try:
                d = fn()
                for k in ("text", "content", "page_content", "pageContent"):
                    if isinstance(d.get(k), str) and d[k].strip():
                        return d[k]
            except Exception:
                pass

    # fallback
    return str(doc)
