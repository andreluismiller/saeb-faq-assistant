import os
import json
import time
import sys

# Adiciona o diretório src ao path para poder importar o módulo RAG
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src')))
from saeb_faq_assistant.rag import RAGSystem

# Configuração de Caminhos
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
GROUND_TRUTH_PATH = os.path.join(BASE_DIR, 'data', 'ground_truth.json')
FAQ_ORIGINAL_PATH = os.path.join(BASE_DIR, 'data', 'faq_saeb.json')
OUTPUT_PATH = os.path.join(BASE_DIR, 'src', 'saeb_faq_assistant', 'eval', 'rag_answers.json')

def carregar_json(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

def salvar_json_incremental(dados, caminho):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def gerar_respostas():
    print("Iniciando geração de respostas do RAG...")
    
    gt_data = carregar_json(GROUND_TRUTH_PATH)
    faq_data = carregar_json(FAQ_ORIGINAL_PATH)
    
    # Criar um dicionário de respostas originais mapeadas por ID para busca em O(1)
    orig_answers_dict = {item['id']: item['answer'] for item in faq_data}
    
    rag = RAGSystem()
    resultados = []
    
    # Carregar progresso anterior, se existir (útil se o script falhar no meio)
    if os.path.exists(OUTPUT_PATH):
        resultados = carregar_json(OUTPUT_PATH)
        ids_processados = {r['id'] for r in resultados}
        print(f"Retomando execução. {len(ids_processados)} respostas já geradas.")
    else:
        ids_processados = set()

    for i, item in enumerate(gt_data, 1):
        item_id = item['id']
        
        if item_id in ids_processados:
            continue
            
        print(f"Processando [{i}/{len(gt_data)}] - ID: {item_id}")
        
        pergunta = item['question']
        resposta_original = orig_answers_dict.get(item_id, "Resposta original não encontrada.")
        
        tentativas = 0
        sucesso = False
        
        while tentativas < 5 and not sucesso:
            try:
                # Executa o pipeline RAG
                rag_result = rag.execute_rag_pipeline(pergunta)
                resposta_llm = rag_result['answer']
                
                # Monta o dicionário de saída
                resultado = {
                    "id": item_id,
                    "survey": item['survey'],
                    "section": item['section'],
                    "question": pergunta,
                    "answer_orig": resposta_original,
                    "answer_llm": resposta_llm
                }
                
                resultados.append(resultado)
                salvar_json_incremental(resultados, OUTPUT_PATH)
                sucesso = True
                
                # Pausa para respeitar limites da API free tier (Groq)
                time.sleep(4) 
                
            except Exception as e:
                erro_msg = str(e).lower()
                if "429" in erro_msg or "rate limit" in erro_msg:
                    tentativas += 1
                    espera = 15 * tentativas # Exponential backoff simples
                    print(f"Rate limit atingido. Aguardando {espera}s (Tentativa {tentativas}/5)...")
                    time.sleep(espera)
                else:
                    print(f"Erro inesperado no ID {item_id}: {e}")
                    break # Pula para o próximo se o erro não for de limite
                    
    print("\n✅ Geração de respostas concluída com sucesso!")

if __name__ == "__main__":
    gerar_respostas()