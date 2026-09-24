import streamlit as st
import pandas as pd
import graphviz
import string

# ==============================================================================
# CONSTRUCCIÓN OPTIMIZADA DE AFN-λ (SIN LAMBDAS REDUNDANTES)
# ==============================================================================

class Estado:
    def __init__(self, id_estado):
        self.id = id_estado
        self.transiciones = {}

    def agregar_transicion(self, simbolo, estado_destino):
        if simbolo not in self.transiciones:
            self.transiciones[simbolo] = []
        if estado_destino not in self.transiciones[simbolo]:
            self.transiciones[simbolo].append(estado_destino)

class AFN:
    def __init__(self, estado_inicial, estado_final, estados_totales=None):
        self.inicial = estado_inicial
        self.final = estado_final
        self.estados = estados_totales if estados_totales is not None else {estado_inicial, estado_final}

    @classmethod
    def crear_simbolo(cls, simbolo, gen_id):
        inicial = Estado(gen_id())
        final = Estado(gen_id())
        inicial.agregar_transicion(simbolo, final)
        return cls(inicial, final)

    def tiene_entrantes(self, estado):
        for e in self.estados:
            for _, dests in e.transiciones.items():
                if estado in dests:
                    return True
        return False

    def tiene_salientes(self, estado):
        return bool(estado.transiciones)

    def concatenacion(self, otro_afn):
        # Fusión si el inicial del segundo autómata no tiene ciclos/entrantes internos
        if not otro_afn.tiene_entrantes(otro_afn.inicial):
            final_viejo = self.final
            inicial_otro = otro_afn.inicial

            for e in otro_afn.estados:
                for s, dests in list(e.transiciones.items()):
                    e.transiciones[s] = [final_viejo if d == inicial_otro else d for d in dests]

            for simbolo, destinos in inicial_otro.transiciones.items():
                for dest in destinos:
                    final_viejo.agregar_transicion(simbolo, dest)

            nuevos_estados = (self.estados | otro_afn.estados) - {inicial_otro}
            return AFN(self.inicial, otro_afn.final, nuevos_estados)
        else:
            # Enlace seguro con una sola lambda si hay lazos que proteger
            self.final.agregar_transicion('λ', otro_afn.inicial)
            nuevos_estados = self.estados | otro_afn.estados
            return AFN(self.inicial, otro_afn.final, nuevos_estados)

    def union(self, otro_afn, gen_id):
        can_merge_init = not self.tiene_entrantes(self.inicial) and not otro_afn.tiene_entrantes(otro_afn.inicial)
        can_merge_final = not self.tiene_salientes(self.final) and not otro_afn.tiene_salientes(otro_afn.final)

        if can_merge_final:
            final_target = self.final
            final_otro = otro_afn.final
            for e in otro_afn.estados:
                for s, dests in list(e.transiciones.items()):
                    e.transiciones[s] = [final_target if d == final_otro else d for d in dests]
            estados_otro = otro_afn.estados - {final_otro}
            nuevo_final = final_target
        else:
            nuevo_final = Estado(gen_id())
            self.final.agregar_transicion('λ', nuevo_final)
            otro_afn.final.agregar_transicion('λ', nuevo_final)
            estados_otro = otro_afn.estados

        if can_merge_init:
            init_target = self.inicial
            init_otro = otro_afn.inicial
            for s, dests in init_otro.transiciones.items():
                for d in dests:
                    init_target.agregar_transicion(s, d)
            estados_otro = estados_otro - {init_otro}
            nuevo_inicial = init_target
        else:
            nuevo_inicial = Estado(gen_id())
            nuevo_inicial.agregar_transicion('λ', self.inicial)
            nuevo_inicial.agregar_transicion('λ', otro_afn.inicial)

        nuevos_estados = self.estados | estados_otro | {nuevo_inicial, nuevo_final}
        return AFN(nuevo_inicial, nuevo_final, nuevos_estados)

    def estrella_kleene(self, gen_id):
        # Si inicial no tiene entrantes y final no tiene salientes, solo agregamos lazo y bypass
        if not self.tiene_entrantes(self.inicial) and not self.tiene_salientes(self.final):
            self.final.agregar_transicion('λ', self.inicial)
            self.inicial.agregar_transicion('λ', self.final)
            return self
        else:
            nuevo_inicial = Estado(gen_id())
            nuevo_final = Estado(gen_id())
            nuevo_inicial.agregar_transicion('λ', self.inicial)
            nuevo_inicial.agregar_transicion('λ', nuevo_final)
            self.final.agregar_transicion('λ', self.inicial)
            self.final.agregar_transicion('λ', nuevo_final)
            nuevos_estados = self.estados | {nuevo_inicial, nuevo_final}
            return AFN(nuevo_inicial, nuevo_final, nuevos_estados)

    def clausura_positiva(self, gen_id):
        if not self.tiene_salientes(self.final):
            self.final.agregar_transicion('λ', self.inicial)
            return self
        else:
            nuevo_final = Estado(gen_id())
            self.final.agregar_transicion('λ', self.inicial)
            self.final.agregar_transicion('λ', nuevo_final)
            nuevos_estados = self.estados | {nuevo_final}
            return AFN(self.inicial, nuevo_final, nuevos_estados)

    def opcional(self, gen_id):
        if not self.tiene_entrantes(self.inicial) and not self.tiene_salientes(self.final):
            self.inicial.agregar_transicion('λ', self.final)
            return self
        else:
            nuevo_inicial = Estado(gen_id())
            nuevo_final = Estado(gen_id())
            nuevo_inicial.agregar_transicion('λ', self.inicial)
            nuevo_inicial.agregar_transicion('λ', nuevo_final)
            self.final.agregar_transicion('λ', nuevo_final)
            nuevos_estados = self.estados | {nuevo_inicial, nuevo_final}
            return AFN(nuevo_inicial, nuevo_final, nuevos_estados)

# ==============================================================================
# PARSER LÉXICO/SINTÁCTICO
# ==============================================================================

def generador_estados():
    contador = 0
    while True:
        yield f"q{contador}"
        contador += 1

ALFABETO = set(string.ascii_letters + string.digits)
OPERADORES_SOPORTADOS = {'|', '*', '+', '?', '(', ')'}

def validar_regex(regex):
    permitidos = ALFABETO | OPERADORES_SOPORTADOS | {'λ'}
    for c in regex:
        if c not in permitidos:
            raise ValueError(f"Carácter no soportado: '{c}'")

def formatear_regex(regex):
    res = ""
    for i in range(len(regex)):
        c1 = regex[i]
        res += c1
        if i + 1 < len(regex):
            c2 = regex[i+1]
            if (c1 in ALFABETO or c1 in "*+?" or c1 == 'λ') and (c2 in ALFABETO or c2 == '(' or c2 == 'λ'):
                res += '.'
            elif c1 == ')' and (c2 in ALFABETO or c2 == '(' or c2 == 'λ'):
                res += '.'
    return res

def infija_a_postfija(regex):
    precedencia = {'*': 3, '+': 3, '?': 3, '.': 2, '|': 1}
    salida = []
    pila = []

    for char in regex:
        if char in ALFABETO or char == 'λ':
            salida.append(char)
        elif char == '(':
            pila.append(char)
        elif char == ')':
            while pila and pila[-1] != '(':
                salida.append(pila.pop())
            if not pila: raise ValueError("Paréntesis desbalanceados")
            pila.pop()
        else:
            while pila and pila[-1] != '(' and precedencia.get(pila[-1], 0) >= precedencia.get(char, 0):
                salida.append(pila.pop())
            pila.append(char)

    while pila:
        if pila[-1] == '(': raise ValueError("Paréntesis desbalanceados")
        salida.append(pila.pop())

    return salida

def construir_afn(postfija):
    pila = []
    gen_id = generador_estados().__next__

    for char in postfija:
        if char in ALFABETO or char == 'λ':
            pila.append(AFN.crear_simbolo(char, gen_id))
        elif char == '*':
            if not pila: raise ValueError("Error en '*'")
            afn = pila.pop()
            pila.append(afn.estrella_kleene(gen_id))
        elif char == '+':
            if not pila: raise ValueError("Error en '+'")
            afn = pila.pop()
            pila.append(afn.clausura_positiva(gen_id))
        elif char == '?':
            if not pila: raise ValueError("Error en '?'")
            afn = pila.pop()
            pila.append(afn.opcional(gen_id))
        elif char == '.':
            if len(pila) < 2: raise ValueError("Error en concatenación")
            afn2 = pila.pop()
            afn1 = pila.pop()
            pila.append(afn1.concatenacion(afn2))
        elif char == '|':
            if len(pila) < 2: raise ValueError("Error en unión")
            afn2 = pila.pop()
            afn1 = pila.pop()
            pila.append(afn1.union(afn2, gen_id))

    return pila[0]

# ==============================================================================
# ALGORITMOS DE MAPEO, λ-CLAUSURA Y CONVERSIONES
# ==============================================================================

def obtener_mapa_estados(afn):
    mapa = {}
    transiciones = []
    alfabeto = set()

    def dfs(estado):
        if estado.id in mapa: return
        mapa[estado.id] = estado
        for simbolo, destinos in estado.transiciones.items():
            if simbolo != 'λ': alfabeto.add(simbolo)
            for dest in destinos:
                transiciones.append((estado.id, simbolo, dest.id))
                dfs(dest)

    dfs(afn.inicial)
    return mapa, transiciones, sorted(list(alfabeto))

def lambda_clausura(estados_ids, mapa_estados):
    pila = list(estados_ids)
    clausura = set(estados_ids)

    while pila:
        actual_id = pila.pop()
        estado_obj = mapa_estados.get(actual_id)
        if estado_obj and 'λ' in estado_obj.transiciones:
            for dest in estado_obj.transiciones['λ']:
                if dest.id not in clausura:
                    clausura.add(dest.id)
                    pila.append(dest.id)

    return clausura

def delta_directo(estados_ids, simbolo, mapa_estados):
    alcanzables = set()
    for eid in estados_ids:
        obj = mapa_estados.get(eid)
        if obj and simbolo in obj.transiciones:
            for dest in obj.transiciones[simbolo]:
                alcanzables.add(dest.id)
    return alcanzables

def afn_lambda_a_afn(afn):
    """
    Construye el AFN sin λ colapsando componentes fuertemente conexas de λ
    y calculando la función de transición canónica sin duplicar arcos redundantes.
    """
    mapa_estados, _, alfabeto = obtener_mapa_estados(afn)
    closures = {s: frozenset(lambda_clausura({s}, mapa_estados)) for s in mapa_estados}

    # Representante canónico para ciclos de λ mutuamente alcanzables
    rep = {}
    for s in mapa_estados:
        ciclo = {t for t in mapa_estados if s in closures[t] and t in closures[s]}
        rep[s] = min(ciclo)

    unique_reps = sorted(list(set(rep.values())))
    renombrar = {r: f"q{i}" for i, r in enumerate(unique_reps)}

    init_state = renombrar[rep[afn.inicial.id]]
    final_states = [renombrar[r] for r in unique_reps if afn.final.id in closures[r]]

    trans_afn = set()
    for r in unique_reps:
        c = closures[r]
        for a in alfabeto:
            alcanzables = delta_directo(c, a, mapa_estados)
            for dest in alcanzables:
                for dest_reach in closures[dest]:
                    trans_afn.add((renombrar[r], a, renombrar[rep[dest_reach]]))

    # Filtrar alcanzables desde el estado inicial
    alcanzables_desde_init = {init_state}
    pila = [init_state]
    while pila:
        curr = pila.pop()
        for orig, a, dest in trans_afn:
            if orig == curr and dest not in alcanzables_desde_init:
                alcanzables_desde_init.add(dest)
                pila.append(dest)

    trans_finales = [t for t in trans_afn if t[0] in alcanzables_desde_init and t[2] in alcanzables_desde_init]
    finales_filtrados = [f for f in final_states if f in alcanzables_desde_init]

    # Re-etiquetado limpio consecutivo (q0, q1, ...)
    estados_activos = sorted(list(alcanzables_desde_init))
    mapeo_limpio = {old: f"q{i}" for i, old in enumerate(estados_activos)}

    init_limpio = mapeo_limpio[init_state]
    finales_limpios = sorted([mapeo_limpio[f] for f in finales_filtrados])
    trans_limpias = sorted([(mapeo_limpio[orig], a, mapeo_limpio[dest]) for orig, a, dest in trans_finales])

    return init_limpio, finales_limpios, trans_limpias, alfabeto

def afn_lambda_a_afd(afn):
    """
    Algoritmo de subconjuntos estándar (Construcción de Thompson/McNaughton-Yamada)
    """
    mapa_estados, _, alfabeto = obtener_mapa_estados(afn)
    start_clausura = lambda_clausura({afn.inicial.id}, mapa_estados)

    etiquetas = {}
    contador = 0

    def get_nombre(conjunto):
        nonlocal contador
        clave = tuple(sorted(list(conjunto)))
        if clave not in etiquetas:
            etiquetas[clave] = f"q{contador}"
            contador += 1
        return etiquetas[clave]

    id_inicial_afd = get_nombre(start_clausura)
    pendientes = [start_clausura]
    procesados = set()
    transiciones_afd = []
    macro_estados = {}

    while pendientes:
        actual_conjunto = pendientes.pop(0)
        clave_actual = tuple(sorted(list(actual_conjunto)))

        if clave_actual in procesados:
            continue
        procesados.add(clave_actual)

        nombre_origen = get_nombre(actual_conjunto)
        macro_estados[nombre_origen] = actual_conjunto

        for a in alfabeto:
            alcanzables_directos = delta_directo(actual_conjunto, a, mapa_estados)
            c2 = lambda_clausura(alcanzables_directos, mapa_estados)

            if c2:
                nombre_destino = get_nombre(c2)
                transiciones_afd.append((nombre_origen, a, nombre_destino))
                if tuple(sorted(list(c2))) not in procesados:
                    pendientes.append(c2)

    finales_afd = [nombre for nombre, conj in macro_estados.items() if afn.final.id in conj]
    return id_inicial_afd, finales_afd, transiciones_afd, alfabeto, macro_estados

def minimizar_afd(id_init, finales, transiciones, alfabeto, macro_estados):
    """
    Minimización de AFD mediante partición de estados equivalentes (Algoritmo de Moore).
    """
    estados_set = set(macro_estados.keys())
    finales_set = set(finales)
    no_finales = estados_set - finales_set

    particiones = []
    if finales_set:
        particiones.append(finales_set)
    if no_finales:
        particiones.append(no_finales)

    delta = {e: {} for e in estados_set}
    for orig, sym, dest in transiciones:
        delta[orig][sym] = dest

    def obtener_grupo(st, parts):
        if st is None: return -1
        for idx, p in enumerate(parts):
            if st in p: return idx
        return -1

    cambio = True
    while cambio:
        cambio = False
        nuevas_particiones = []
        for grupo in particiones:
            if len(grupo) <= 1:
                nuevas_particiones.append(grupo)
                continue
            subgrupos = {}
            for st in grupo:
                firma = tuple(obtener_grupo(delta[st].get(a, None), particiones) for a in alfabeto)
                if firma not in subgrupos:
                    subgrupos[firma] = set()
                subgrupos[firma].add(st)
            if len(subgrupos) > 1:
                cambio = True
            for sg in subgrupos.values():
                nuevas_particiones.append(sg)
        particiones = nuevas_particiones

    init_grupo = [g for g in particiones if id_init in g][0]
    otros_grupos = [g for g in particiones if g != init_grupo]
    grupos_ordenados = [init_grupo] + sorted(otros_grupos, key=lambda g: sorted(list(g))[0])

    renombrar = {}
    for i, g in enumerate(grupos_ordenados):
        nombre = f"q{i}"
        for st in g:
            renombrar[st] = nombre

    nuevos_estados = [f"q{i}" for i in range(len(grupos_ordenados))]
    nuevo_init = renombrar[id_init]
    nuevos_finales = sorted(list(set(renombrar[st] for st in finales_set)))

    nuevas_trans = set()
    for orig, sym, dest in transiciones:
        nuevas_trans.add((renombrar[orig], sym, renombrar[dest]))

    mapeo_grupos = {f"q{i}": sorted(list(g)) for i, g in enumerate(grupos_ordenados)}
    return nuevo_init, nuevos_finales, sorted(list(nuevas_trans)), nuevos_estados, mapeo_grupos

def simular_afd(id_init, finales, transiciones, cadena):
    """
    Simula la ejecución de una cadena sobre el AFD y retorna la traza paso a paso.
    """
    delta = {}
    for orig, sym, dest in transiciones:
        if orig not in delta:
            delta[orig] = {}
        delta[orig][sym] = dest

    pasos = []
    actual = id_init

    if not cadena:
        es_final = actual in finales
        return es_final, [(actual, "λ", actual)], "Cadena vacía"

    for char in cadena:
        if actual in delta and char in delta[actual]:
            siguiente = delta[actual][char]
            pasos.append((actual, char, siguiente))
            actual = siguiente
        else:
            pasos.append((actual, char, "∅ (Bloqueo)"))
            return False, pasos, f"Bloqueo: No existe transición desde '{actual}' con el símbolo '{char}'"

    es_final = actual in finales
    return es_final, pasos, "Cadena Aceptada" if es_final else f"Cadena Rechazada: El estado final '{actual}' no es de aceptación"

# ==============================================================================
# HELPERS DE RENDERIZADO GRAPHVIZ
# ==============================================================================

def generar_grafo_dot(id_init, finales, transiciones, estados=None, es_lambda=False):
    dot = graphviz.Digraph()
    dot.attr(rankdir='LR', size='12,8', bgcolor='transparent')
    dot.attr('node', fontname='Helvetica', fontsize='11', shape='circle', style='filled', fillcolor='#F8F9FA', color='#343A40')
    dot.attr('edge', fontname='Helvetica', fontsize='10', color='#495057')

    # Nodo apuntador de inicio
    dot.node('start', shape='point', style='invis')
    dot.edge('start', id_init, label='', color='#2E7D32', penwidth='1.8')

    todos_los_estados = set(estados) if estados else set()
    todos_los_estados.add(id_init)
    for orig, _, dest in transiciones:
        todos_los_estados.add(orig)
        todos_los_estados.add(dest)

    for eid in sorted(list(todos_los_estados)):
        if eid in finales:
            dot.node(eid, shape='doublecircle', fillcolor='#E8F5E9' if eid == id_init else '#FFEBEE', 
                     color='#2E7D32' if eid == id_init else '#C62828', penwidth='2.0')
        elif eid == id_init:
            dot.node(eid, shape='circle', fillcolor='#E8F5E9', color='#2E7D32', penwidth='2.0')
        else:
            dot.node(eid, shape='circle')

    # Agrupar transiciones paralelas
    trans_agrupadas = {}
    for orig, sym, dest in transiciones:
        clave = (orig, dest)
        if clave not in trans_agrupadas:
            trans_agrupadas[clave] = set()
        trans_agrupadas[clave].add(sym)

    for (orig, dest), simbolos in trans_agrupadas.items():
        simbolos_ordenados = sorted(list(simbolos))
        label = ",".join(simbolos_ordenados)
        if 'λ' in simbolos:
            dot.edge(orig, dest, label=label, color='#E65100', fontcolor='#E65100', style='dashed', penwidth='1.5')
        else:
            dot.edge(orig, dest, label=label, color='#1565C0', fontcolor='#0D47A1', penwidth='1.2')

    return dot

# ==============================================================================
# INTERFAZ STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Conversor Optimizado de ER a Autómatas", layout="wide", page_icon="⚡")

st.title("⚡ Conversor Optimizado de ER a Autómatas")
st.markdown("""
Esta versión optimizada implementa **reducción de transiciones λ en tiempo de construcción**, 
**fusión de estados compatibles** y **colapso de ciclos λ** para producir autómatas 
limpios, comprensibles y sin sobrecarga visual.
""")

col_input, col_ejemplos = st.columns([3, 1])

with col_ejemplos:
    ejemplo = st.selectbox(
        "Cargar ejemplo:",
        ["(a|b)*abb", "(a|b)*", "a*b*", "(a*b)*", "a+b+", "(a|b)+", "a|b|c", "(ab|cd)*", "(a|λ)b"]
    )

with col_input:
    regex_input = st.text_input("Ingresa la Expresión Regular:", value=ejemplo)

if regex_input:
    try:
        validar_regex(regex_input)
        regex_formateada = formatear_regex(regex_input)
        postfija = infija_a_postfija(regex_formateada)
        afn = construir_afn(postfija)

        mapa_estados, trans_lambda, alfabeto = obtener_mapa_estados(afn)
        lambdas_totales = [t for t in trans_lambda if t[1] == 'λ']

        tab1, tab2, tab3, tab4 = st.tabs([
            "1. AFN-λ Optimizado", 
            "2. AFN (Sin λ)", 
            "3. AFD (Subconjuntos)",
            "4. AFD Mínimo & Simulador"
        ])

        # ======================================================================
        # TAB 1: AFN-λ OPTIMIZADO
        # ======================================================================
        with tab1:
            st.subheader("1. AFN-λ (Thompson Reducido al Mínimo)")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Estados", len(mapa_estados))
            m2.metric("Transiciones Totales", len(trans_lambda))
            m3.metric("Transiciones λ", len(lambdas_totales))
            m4.metric("Alfabeto", f"{{{', '.join(alfabeto)}}}")

            col_t1, col_t2 = st.columns([1, 2])

            with col_t1:
                st.markdown("#### Matriz de Transiciones AFN-λ")
                cols_tabla = alfabeto + (['λ'] if lambdas_totales else [])
                estados_ordenados = sorted(list(mapa_estados.keys()))
                df_lambda = pd.DataFrame(index=estados_ordenados, columns=cols_tabla).fillna("∅")

                for orig, sym, dest in trans_lambda:
                    val_actual = df_lambda.loc[orig, sym]
                    df_lambda.loc[orig, sym] = dest if val_actual == "∅" else f"{val_actual}, {dest}"

                st.dataframe(df_lambda, use_container_width=True)
                st.write(f"🟢 **Estado Inicial:** `{afn.inicial.id}`")
                st.write(f"🔴 **Estado Final:** `{afn.final.id}`")

            with col_t2:
                st.markdown("#### Grafo del AFN-λ")
                dot_lambda = generar_grafo_dot(afn.inicial.id, [afn.final.id], trans_lambda, mapa_estados.keys(), es_lambda=True)
                st.graphviz_chart(dot_lambda, use_container_width=True)

        # ======================================================================
        # TAB 2: AFN SIN LAMBDAS
        # ======================================================================
        with tab2:
            st.subheader("2. AFN Canónico (Sin Transiciones λ)")
            init_afn, finales_afn, trans_afn, alf = afn_lambda_a_afn(afn)
            estados_unicos_afn = sorted(list(set([t[0] for t in trans_afn] + [t[2] for t in trans_afn] + [init_afn])))

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Estados", len(estados_unicos_afn))
            m2.metric("Transiciones", len(trans_afn))
            m3.metric("Estado Inicial", init_afn)
            m4.metric("Estados Finales", f"{{{', '.join(finales_afn)}}}")

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("#### Matriz AFN (Sin λ)")
                df_afn = pd.DataFrame(index=estados_unicos_afn, columns=alf).fillna("∅")

                for orig, sym, dest in trans_afn:
                    val = df_afn.loc[orig, sym]
                    df_afn.loc[orig, sym] = dest if val == "∅" else f"{val}, {dest}"

                st.dataframe(df_afn, use_container_width=True)
                st.info("💡 Construido mediante clausura-λ colapsando ciclos mutuos para evitar arcos inflados.")

            with col2:
                st.markdown("#### Grafo del AFN (Sin λ)")
                dot_afn = generar_grafo_dot(init_afn, finales_afn, trans_afn, estados_unicos_afn)
                st.graphviz_chart(dot_afn, use_container_width=True)

        # ======================================================================
        # TAB 3: AFD (SUBCONJUNTOS)
        # ======================================================================
        with tab3:
            st.subheader("3. AFD (Construcción de Subconjuntos)")
            init_afd, finales_afd, trans_afd, alf, macro_est = afn_lambda_a_afd(afn)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Estados AFD", len(macro_est))
            m2.metric("Transiciones AFD", len(trans_afd))
            m3.metric("Estado Inicial", init_afd)
            m4.metric("Estados Finales", f"{{{', '.join(finales_afd)}}}")

            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("#### Matriz AFD")
                df_afd = pd.DataFrame(index=sorted(macro_est.keys()), columns=alf).fillna("∅")
                for orig, sym, dest in trans_afd:
                    df_afd.loc[orig, sym] = dest
                st.dataframe(df_afd, use_container_width=True)

                st.markdown("#### Mapeo de Macro-Estados")
                mapeo_data = []
                for nombre in sorted(macro_est.keys()):
                    conj = sorted(list(macro_est[nombre]))
                    es_fin = "✓ Sí" if nombre in finales_afd else "No"
                    mapeo_data.append({
                        "Estado AFD": nombre,
                        "Subconjunto AFN-λ": f"{{{', '.join(conj)}}}",
                        "Aceptación": es_fin
                    })
                st.dataframe(pd.DataFrame(mapeo_data), use_container_width=True, hide_index=True)

            with col2:
                st.markdown("#### Grafo del AFD")
                dot_afd = generar_grafo_dot(init_afd, finales_afd, trans_afd, macro_est.keys())
                st.graphviz_chart(dot_afd, use_container_width=True)

        # ======================================================================
        # TAB 4: AFD MÍNIMO & SIMULADOR
        # ======================================================================
        with tab4:
            st.subheader("4. AFD Mínimo & Simulador de Cadenas")

            min_init, min_finales, min_trans, min_estados, mapeo_min = minimizar_afd(
                init_afd, finales_afd, trans_afd, alf, macro_est
            )

            col_min1, col_min2 = st.columns([1, 2])

            with col_min1:
                st.markdown("#### Matriz AFD Mínimo (Algoritmo de Moore)")
                if len(min_estados) == len(macro_est):
                    st.success(f"El AFD obtenido por subconjuntos ya es mínimo ({len(min_estados)} estados).")
                else:
                    st.info(f"El AFD fue reducido de {len(macro_est)} a {len(min_estados)} estados equivalentes.")

                df_min = pd.DataFrame(index=min_estados, columns=alf).fillna("∅")
                for orig, sym, dest in min_trans:
                    df_min.loc[orig, sym] = dest
                st.dataframe(df_min, use_container_width=True)

                st.markdown("#### Fusión de Estados Equivalentes")
                fusions_data = [{"Estado Mínimo": k, "Estados AFD Agrupados": f"{{{', '.join(v)}}}"} for k, v in mapeo_min.items()]
                st.dataframe(pd.DataFrame(fusions_data), use_container_width=True, hide_index=True)

            with col_min2:
                st.markdown("#### Grafo del AFD Mínimo")
                dot_min = generar_grafo_dot(min_init, min_finales, min_trans, min_estados)
                st.graphviz_chart(dot_min, use_container_width=True)

            st.markdown("---")
            st.subheader("🧪 Simulador de Cadenas en el AFD")
            test_cadena = st.text_input("Ingresa una cadena para evaluar:", value="abb")

            if st.button("Evaluar Cadena"):
                es_valida, traza, mensaje = simular_afd(min_init, min_finales, min_trans, test_cadena)

                if es_valida:
                    st.success(f"🎉 **{mensaje}**")
                else:
                    st.error(f"❌ **{mensaje}**")

                st.markdown("##### Recorrido de Estados:")
                traza_df = []
                for idx, (origen, sym, destino) in enumerate(traza):
                    traza_df.append({
                        "Paso": idx + 1,
                        "Estado Actual": origen,
                        "Símbolo Consumido": sym if sym else "-",
                        "Siguiente Estado": destino
                    })
                st.dataframe(pd.DataFrame(traza_df), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error procesando la expresión regular: {e}")
