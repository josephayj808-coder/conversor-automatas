import streamlit as st
import pandas as pd
import graphviz

# --- ESTRUCTURAS DE DATOS (Basado en "Autómatas ", Teorema de Kleene Parte I) ---

class Estado:
    def __init__(self, id_estado):
        self.id = id_estado
        self.transiciones = {} 

    def agregar_transicion(self, simbolo, estado_destino):
        if simbolo not in self.transiciones:
            self.transiciones[simbolo] = []
        self.transiciones[simbolo].append(estado_destino)

class AFN:
    def __init__(self, estado_inicial, estado_final):
        self.inicial = estado_inicial
        self.final = estado_final 

    @classmethod
    def crear_simbolo(cls, simbolo, gen_id):
        # Caso base: crear autómata para un símbolo 'a' o 'λ'
        inicial = Estado(gen_id())
        final = Estado(gen_id())
        inicial.agregar_transicion(simbolo, final)
        return cls(inicial, final)

    def concatenacion(self, otro_afn):
        # Operación: Concatenación (RS). Transición λ desde el final de R al inicial de S
        self.final.agregar_transicion('λ', otro_afn.inicial)
        return AFN(self.inicial, otro_afn.final)

    def union(self, otro_afn, gen_id):
        # Operación: Unión (R U S). Nuevo estado inicial y final con transiciones λ
        nuevo_inicial = Estado(gen_id())
        nuevo_final = Estado(gen_id())
        
        nuevo_inicial.agregar_transicion('λ', self.inicial)
        nuevo_inicial.agregar_transicion('λ', otro_afn.inicial)
        
        self.final.agregar_transicion('λ', nuevo_final)
        otro_afn.final.agregar_transicion('λ', nuevo_final)
        
        return AFN(nuevo_inicial, nuevo_final)

    def estrella_kleene(self, gen_id):
        # Operación: Estrella de Kleene (R*). 
        nuevo_inicial = Estado(gen_id())
        nuevo_final = Estado(gen_id())
        
        nuevo_inicial.agregar_transicion('λ', self.inicial)
        nuevo_inicial.agregar_transicion('λ', nuevo_final)
        
        self.final.agregar_transicion('λ', self.inicial)
        self.final.agregar_transicion('λ', nuevo_final)
        
        return AFN(nuevo_inicial, nuevo_final)

# --- FUNCIONES AUXILIARES ---

def generador_estados():
    contador = 0
    while True:
        yield f"q{contador}"
        contador += 1

def formatear_regex(regex):
    """Inserta operadores de concatenación '.' explícitos para facilitar el parseo."""
    res = ""
    alfabeto = set("abcdefghijklmnopqrstuvwxyz0123456789")
    for i in range(len(regex)):
        c1 = regex[i]
        res += c1
        if i + 1 < len(regex):
            c2 = regex[i+1]
            if (c1 in alfabeto or c1 in "*+") and (c2 in alfabeto or c2 == "("):
                res += '.'
            elif c1 == ")" and (c2 in alfabeto or c2 == "("):
                res += '.'
    return res

def infija_a_postfija(regex):
    precedencia = {'*': 3, '.': 2, '|': 1}
    salida = []
    pila = []
    
    for char in regex:
        if char.isalnum() or char == 'λ':
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
    pila = []
    gen_id = generador_estados().__next__
    
    for char in postfija:
        if char.isalnum() or char == 'λ':
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
    visitados = set()
    transiciones = []
    alfabeto = set()
    
    def dfs(estado):
        if estado.id in visitados: return
        visitados.add(estado.id)
        for simbolo, destinos in estado.transiciones.items():
            alfabeto.add(simbolo)
            for dest in destinos:
                transiciones.append((estado.id, simbolo, dest.id))
                dfs(dest)
                
    dfs(afn.inicial)
    return transiciones, sorted(list(alfabeto))

# --- INTERFAZ STREAMLIT ---

st.title("Conversor de Expresiones Regulares a AFN-λ")
st.markdown("Basado en el **Teorema de Kleene. Parte I**")

regex_input = st.text_input("Ingresa la Expresión Regular (usa '|' para unión, '*' para Kleene):")

if st.button("Generar Autómata"):
    if regex_input:
        try:
            # 1. Validación y Parseo
            regex_formateada = formatear_regex(regex_input)
            postfija = infija_a_postfija(regex_formateada)
            
            # 2. Construcción del AFN
            afn = construir_afn(postfija)
            transiciones, alfabeto = obtener_transiciones(afn)
            
            st.success("¡Expresión regular procesada correctamente!")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Función de Transición")
                # Crear diccionario para mostrar la función
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
                # Crear DataFrame de Pandas
                df_dict = {}
                estados_unicos = sorted(list(set([t[0] for t in transiciones] + [t[2] for t in transiciones])))
                
                for estado in estados_unicos:
                    df_dict[estado] = {sym: "∅" for sym in alfabeto}
                    
                for origen, simbolo, destino in transiciones:
                    if df_dict[origen][simbolo] == "∅":
                        df_dict[origen][simbolo] = destino
                    else:
                        df_dict[origen][simbolo] += f", {destino}"
                        
                df = pd.DataFrame.from_dict(df_dict, orient='index')
                st.dataframe(df)

            st.subheader("Grafo del AFN-λ")
            # Construir Grafo con Graphviz
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR')
            
            # Nodo inicial oculto para la flecha de entrada
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
    else:
        st.warning("Por favor, ingresa una expresión regular.")