from duckduckgo_search import DDGS

def search_web(query, max_results=3):
    """
    Realiza una busqueda web a traves de DuckDuckGo API y devuelve un string formateado.
    """
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No se encontraron resultados relevantes."
            
        formatted_results = []
        for index, r in enumerate(results):
            formatted_results.append(f"[{index + 1}] {r.get('title', 'Sin titulo')}\n    Fragmento: {r.get('body', 'Sin contenido')}")
            
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Error en busqueda web: {str(e)}"
