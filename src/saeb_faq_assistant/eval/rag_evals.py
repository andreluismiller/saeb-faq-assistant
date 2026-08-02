import os
import json
import time
from openai import OpenAI

# Configuração de Caminhos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
INPUT_PATH = os.path.join(BASE_DIR, 'src', 'saeb_faq_assistant', 'eval', 'rag_answers.json')
ATA_OUTPUT_PATH = os.path.join(BASE_DIR, 'src', 'saeb_faq_assistant', 'eval', 'ata_results.json')
QTA_OUTPUT_PATH = os.path.join(BASE_DIR, 'src', 'saeb_faq_assistant', 'eval', 'qta_results.json')

# Cliente LLM para Avaliação
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)
EVAL_MODEL = "llama-3.3-70b-versatile"

def carregar_json(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_json(dados, caminho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def avaliar_com_llm(prompt_sistema, prompt_usuario):
    """Envia o prompt para o LLM forçando a saída em JSON nativo."""
    try:
        response = client.chat.completions.create(
            model=EVAL_MODEL,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.0, # Temperatura 0 para avaliação o mais determinística possível
            response_format={"type": "json_object"}
        )
        conteudo = response.choices[0].message.content
        return json.loads(conteudo)
    except Exception as e:
        raise e

def executar_avaliacao_ata(dados):
    """ATA: Answer-To-Answer (Compara Resposta Gerada vs Resposta Original)"""
    print("\n--- Iniciando Avaliação ATA (Answer-To-Answer) ---")
    resultados_ata = carregar_json(ATA_OUTPUT_PATH)
    ids_processados = {r['id'] for r in resultados_ata}
    
    prompt_sistema = """
Você é um avaliador especialista. Sua tarefa é comparar uma Resposta Gerada por IA com uma Resposta Original de Referência.
Atribua um 'score' baseado nos seguintes critérios:
- "bom": A Resposta Gerada contém todas as informações vitais da Resposta Original e é correta.
- "mediano": A Resposta Gerada é parcialmente correta ou omite detalhes importantes presentes na original.
- "ruim": A Resposta Gerada é incorreta, contradiz a Original, ou alucina informações.

Você DEVE retornar APENAS um objeto JSON no formato exato:
{"score": "bom|mediano|ruim", "reasoning": "Sua explicação passo a passo em português do Brasil"}
"""

    for i, item in enumerate(dados, 1):
        if item['id'] in ids_processados:
            continue
            
        print(f"ATA - Avaliando [{i}/{len(dados)}] - ID: {item['id']}")
        
        prompt_usuario = f"""
Resposta Original de Referência:
{item['answer_orig']}

Resposta Gerada pela IA:
{item['answer_llm']}
"""
        tentativas = 0
        while tentativas < 5:
            try:
                avaliacao = avaliar_com_llm(prompt_sistema, prompt_usuario)
                
                resultado = item.copy()
                resultado['ata_score'] = avaliacao.get('score', 'erro')
                resultado['ata_reasoning'] = avaliacao.get('reasoning', 'sem explicação')
                
                resultados_ata.append(resultado)
                salvar_json(resultados_ata, ATA_OUTPUT_PATH)
                time.sleep(3) # Pausa para rate limit Groq
                break
            except Exception as e:
                tentativas += 1
                espera = 10 * tentativas
                print(f"Erro na API (ATA). Tentando de novo em {espera}s... ({e})")
                time.sleep(espera)

def executar_avaliacao_qta(dados):
    """QTA: Question-To-Answer (Avalia se a resposta atende à pergunta)"""
    print("\n--- Iniciando Avaliação QTA (Question-To-Answer) ---")
    resultados_qta = carregar_json(QTA_OUTPUT_PATH)
    ids_processados = {r['id'] for r in resultados_qta}
    
    prompt_sistema = """
Você é um avaliador especialista. Sua tarefa é verificar o quão bem uma Resposta Gerada responde diretamente à Pergunta Feita.
Atribua um 'score' baseado nos seguintes critérios:
- "bom": A resposta atende completa e diretamente à pergunta, sem rodeios e de forma correta.
- "mediano": A resposta atende à pergunta parcialmente ou inclui informações tangenciais não solicitadas que confundem.
- "ruim": A resposta falha em responder à pergunta central ou fornece informações totalmente irrelevantes.

Você DEVE retornar APENAS um objeto JSON no formato exato:
{"score": "bom|mediano|ruim", "reasoning": "Sua explicação passo a passo em português do Brasil"}
"""

    for i, item in enumerate(dados, 1):
        if item['id'] in ids_processados:
            continue
            
        print(f"QTA - Avaliando [{i}/{len(dados)}] - ID: {item['id']}")
        
        prompt_usuario = f"""
Pergunta do Usuário:
{item['question']}

Resposta Gerada pela IA a ser avaliada:
{item['answer_llm']}
"""
        tentativas = 0
        while tentativas < 5:
            try:
                avaliacao = avaliar_com_llm(prompt_sistema, prompt_usuario)
                
                resultado = item.copy()
                resultado['qta_score'] = avaliacao.get('score', 'erro')
                resultado['qta_reasoning'] = avaliacao.get('reasoning', 'sem explicação')
                
                resultados_qta.append(resultado)
                salvar_json(resultados_qta, QTA_OUTPUT_PATH)
                time.sleep(3) # Pausa para rate limit Groq
                break
            except Exception as e:
                tentativas += 1
                espera = 10 * tentativas
                print(f"Erro na API (QTA). Tentando de novo em {espera}s... ({e})")
                time.sleep(espera)

if __name__ == "__main__":
    if not os.path.exists(INPUT_PATH):
        print(f"Arquivo {INPUT_PATH} não encontrado. Execute 'generate_answers.py' primeiro.")
    else:
        dados = carregar_json(INPUT_PATH)
        executar_avaliacao_ata(dados)
        executar_avaliacao_qta(dados)
        print("\n✅ Todas as avaliações foram concluídas!")