import streamlit as st
import pandas as pd
import graphviz
import string

# ==============================================================================
# ESTRUCTURAS DE DATOS BASE
# Implementación orientada a objetos del Teorema de Kleene (Parte I)
# ==============================================================================

class Estado:
    """
    Representa un nodo en el grafo del autómata.
    Se utiliza un diccionario para las transiciones porque permite búsquedas O(1).
    La clave es el símbolo (ej. 'a', 'b', 'λ') y el valor es una lista de estados destino,
    garantizando que se modele correctamente el No-Determinismo.
    """
    def __init__(self, id_estado):
        self.id = id_estado
        self.transiciones = {}

    def agregar_transicion(self, simbolo, estado_destino):
        if simbolo not in self.transiciones:
            self.transiciones[simbolo] = []
        self.transiciones[simbolo].append(estado_destino)

class AFN:
    """
    Modela un Autómata Finito No Determinista con un único estado inicial y final.
    Esta estructura modular permite encadenar autómatas pequeños para construir 
    uno más grande, siguiendo las reglas inductivas del Teorema de Kleene.
    """
    def __init__(self, estado_inicial, estado_final):
        self.inicial = estado_inicial
        self.final = estado_final

    @classmethod
    def crear_simbolo(cls, simbolo, gen_id):
        # CASO BASE: Crea un mini-autómata de dos estados conectados por un símbolo o por λ.
        inicial = Estado(gen_id())
        final = Estado(gen_id())
        inicial.agregar_transicion(simbolo, final)
        return cls(inicial, final)

    def concatenacion(self, otro_afn):
        # OPERACIÓN: Concatenación (RS).
        # Para la sustentación: Aquí se prioriza la exactitud formal del Teorema de Kleene. 
        # Se conecta el estado final del primer bloque con el inicial del segundo 
        # a través de una transición espontánea 'λ', sin fusionar estados.
        self.final.agregar_transicion('λ', otro_afn.inicial)
        return AFN(self.inicial, otro_afn.final)

    def union(self, otro_afn, gen_id):
        # OPERACIÓN: Unión (R U S). 
        # Crea un nuevo estado inicial que se bifurca con 'λ' hacia las dos opciones,
        # y un nuevo estado final donde convergen los resultados mediante 'λ'.
        # Esto preserva el no-determinismo puro sin consumir caracteres de la cinta.
        nuevo_inicial = Estado(gen_id())
        nuevo_final = Estado(gen_id())
        nuevo_inicial.agregar_transicion('λ', self.inicial)
        nuevo_inicial.agregar_transicion('λ', otro_afn.inicial)
        self.final.agregar_transicion('λ', nuevo_final)
        otro_afn.final.agregar_transicion('λ', nuevo_final)
        return AFN(nuevo_inicial, nuevo_final)

    def estrella_kleene(self, gen_id):
        # OPERACIÓN: Estrella de Kleene (R*).
        # Permite cero repeticiones (puente directo al final) o múltiples repeticiones 
        # (retorno al inicio del bloque). Se usan transiciones 'λ' para no alterar 
        # la longitud de la cadena procesada.
        nuevo_inicial = Estado(gen_id())
        nuevo_final = Estado(gen_id())
        nuevo_inicial.agregar_transicion('λ', self.inicial)
        nuevo_inicial.agregar_transicion('λ', nuevo_final)
        self.final.agregar_transicion('λ', self.inicial)
        self.final.agregar_transicion('λ', nuevo_final)
        return AFN(nuevo_inicial, nuevo_final)

# ==============================================================================
# ANALIZADOR LÉXICO Y SINTÁCTICO (PARSER)
# ==============================================================================

def generador_estados():
    # Generador perezoso (yield) para proveer identificadores secuenciales únicos (q0, q1...).
    contador = 0
    while True:
        yield f"q{contador}"
        contador += 1

ALFABETO = set(string.ascii_letters + string.digits + "λ")
OPERADORES_SOPORTADOS = {'|', '*', '(', ')'}

def validar_regex(regex):
    """
    Filtro de seguridad (Whitelist). Previene inyecciones de caracteres inválidos 
    y asegura que el autómata solo intente graficar símbolos reconocidos matemáticamente.
    """
    permitidos = ALFABETO | OPERADORES_SOPORTADOS
    for c in regex:
        if c not in permitidos:
            raise ValueError(f"Carácter no soportado: '{c}'. Alcance del proyecto: solo "
                              f"símbolos alfanuméricos, 'λ', '|', '*' y paréntesis.")

def formatear_regex(regex):
    """
    Inserta el operador de concatenación explícito ('.').
    Matemáticamente escribimos 'ab', pero computacionalmente necesitamos evaluar 'a.b'
    para saber en qué momento exacto aplicar la función de concatenación.
    """
    res = ""
    for i in range(len(regex)):
        c1 = regex[i]
        res += c1
        if i + 1 < len(regex):
            c2 = regex[i+1]
            if (c1 in ALFABETO or c1 == "*") and (c2 in ALFABETO or c2 == "("):
                res += '.'
            elif c1 == ")" and (c2 in ALFABETO or c2 == "("):
                res += '.'
    return res

def infija_a_postfija(regex):
    """
    Algoritmo de Shunting Yard (Dijkstra).
    Convierte la notación humana (infija: a|b) a notación para la máquina (postfija: ab|).
    Esto elimina la necesidad de evaluar precedencia y paréntesis durante la construcción del grafo.
    """
    precedencia = {'*': 3, '.': 2, '|': 1}
    salida = []
    pila = []
    
    for char in regex:
        if char in ALFABETO:
            salida.append(char)
        elif char == '(':
            pila.append(char)
        elif char == ')':
            while pila and pila[-1] != '(':
                salida.append(pila.pop())
            if not pila:
                raise ValueError("Paréntesis desbalanceados")
            pila.pop()
        else:
            while pila and pila[-1] != '(' and precedencia.get(pila[-1], 0) >= precedencia.get(char, 0):
                salida.append(pila.pop())
            pila.append(char)
            
    while pila:
        if pila[-1] == '(':
            raise ValueError("Paréntesis desbalanceados")
        salida.append(pila.pop())
        
    return salida

def construir_afn(postfija):
    """
    Máquina de pila que evalúa la cadena postfija de izquierda a derecha.
    Si es un símbolo, instancia el caso base. Si es un operador, extrae los autómatas 
    previos de la pila, los fusiona según las reglas del Teorema de Kleene y devuelve 
    el super-autómata resultante a la pila.
    """
    pila = []
    gen_id = generador_estados().__next__
    
    for char in postfija:
        if char in ALFABETO:
            pila.append(AFN.crear_simbolo(char, gen_id))
        elif char == '*':
            if not pila: raise ValueError("Error de sintaxis: '*' sin operando")
            afn = pila.pop()
            pila.append(afn.estrella_kleene(gen_id))
        elif char == '.':
            if len(pila) < 2: raise ValueError("Error de sintaxis: falta operando para concatenación")
            afn2 = pila.pop()
            afn1 = pila.pop()
            pila.append(afn1.concatenacion(afn2))
        elif char == '|':
            if len(pila) < 2: raise ValueError("Error de sintaxis: falta operando para unión")
            afn2 = pila.pop()
            afn1 = pila.pop()
            pila.append(afn1.union(afn2, gen_id))
            
    if len(pila) != 1:
        raise ValueError("Expresión regular inválida")
        
    return pila[0]

def obtener_transiciones(afn):
    """
    Recorrido en profundidad (DFS) para mapear todos los nodos del grafo.
    Extrae la matriz lógica necesaria para alimentar a Pandas y Graphviz.
    """
    visitados = set()
    transiciones = []
    alfabeto_usado = set()
    
    def dfs(estado):
        if estado.id in visitados: return
        visitados.add(estado.id)
        for simbolo, destinos in estado.transiciones.items():
            alfabeto_usado.add(simbolo)
            for dest in destinos:
                transiciones.append((estado.id, simbolo, dest.id))
                dfs(dest)
                
    dfs(afn.inicial)
    return transiciones, sorted(list(alfabeto_usado))

# ==============================================================================
# INTERFAZ WEB (STREAMLIT)
# ==============================================================================

st.title("Conversor de Expresiones Regulares a AFN-λ")
st.markdown("Basado en el **Teorema de Kleene. Parte I**")

regex_input = st.text_input("Ingresa la Expresión Regular (usa '|' para unión, '*' para Kleene):")

if st.button("Generar Autómata"):
    if regex_input:
        try:
            validar_regex(regex_input)
            regex_formateada = formatear_regex(regex_input)
            postfija = infija_a_postfija(regex_formateada)
            afn = construir_afn(postfija)
            transiciones, alfabeto_usado = obtener_transiciones(afn)
            
            st.success("¡Expresión regular procesada correctamente!")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Función de Transición")
                func_trans = {}
                for origen, simbolo, destino in transiciones:
                    clave = f"δ({origen}, {simbolo})"
                    if clave in func_trans:
                        func_trans[clave].append(destino)
                    else:
                        func_trans[clave] = [destino]
                        
                for k, v in func_trans.items():
                    st.write(f"{k} = {{ {', '.join(v)} }}")
                    
                st.write(f"**Estado Inicial:** {afn.inicial.id}")
                st.write(f"**Estado Final:** {afn.final.id}")

            with col2:
                st.subheader("Matriz de Transición")
                df_dict = {}
                estados_unicos = sorted(list(set([t[0] for t in transiciones] + [t[2] for t in transiciones])))
                
                for estado in estados_unicos:
                    df_dict[estado] = {sym: "∅" for sym in alfabeto_usado}
                    
                for origen, simbolo, destino in transiciones:
                    if df_dict[origen][simbolo] == "∅":
                        df_dict[origen][simbolo] = destino
                    else:
                        df_dict[origen][simbolo] += f", {destino}"
                        
                df = pd.DataFrame.from_dict(df_dict, orient='index')
                st.dataframe(df)

            st.subheader("Grafo del AFN-λ")
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR')
            dot.node('start', shape='point')
            dot.edge('start', afn.inicial.id)
            
            for estado in estados_unicos:
                if estado == afn.final.id:
                    dot.node(estado, shape='doublecircle')
                else:
                    dot.node(estado, shape='circle')
                    
            for origen, simbolo, destino in transiciones:
                dot.edge(origen, destino, label=simbolo)
                
            st.graphviz_chart(dot)

        except ValueError as e:
            st.error(f"Error de validación: {e}")
        except RecursionError:
            st.error("La expresión es demasiado grande/anidada para procesarse. "
                     "Intenta simplificarla o dividirla en partes más pequeñas.")
    else:
        st.warning("Por favor, ingresa una expresión regular.")
