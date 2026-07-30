import requests
from bs4 import BeautifulSoup
import json

from src.saeb_faq_assistant.paths import DATASET_PATH

def scrape_saeb_faq():
    url = "https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/sistema-de-avaliacao-da-educacao-basica-saeb"
    
    # Cabeçalho para simular um navegador real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Erro ao acessar a página: {response.status_code}")
        return
        
    soup = BeautifulSoup(response.content, "html.parser")
    
    faq_list = []
    current_id = 1
    
    # Localiza o container principal do conteúdo da página
    content_core = soup.find('div', id='content-core')
    if not content_core:
        print("Não foi possível encontrar a div#content-core.")
        return

    # A primeira lista (ul) dentro de content-core contém as seções
    main_ul = content_core.find('ul')
    if not main_ul:
        print("Não foi possível encontrar a lista de seções.")
        return
        
    # Itera sobre os itens (li) do primeiro nível, que representam as Seções
    # O parâmetro recursive=False garante que pegaremos apenas os <li> diretos da main_ul
    for section_li in main_ul.find_all('li', recursive=False):
        
        # O título da seção está na tag <a> com classe 'toggle'
        section_a = section_li.find('a', class_='toggle')
        if not section_a:
            continue
            
        section_name = section_a.get_text(strip=True)
        
        # A sublista (ul) dentro deste item contém as perguntas da respectiva seção
        questions_ul = section_li.find('ul')
        if not questions_ul:
            continue
            
        # Itera sobre os itens (li) da sublista, que representam as Perguntas
        for q_li in questions_ul.find_all('li', recursive=False):
            question_a = q_li.find('a', class_='toggle')
            answer_div = q_li.find('div', class_='conteudo')
            
            # Se encontrou ambos (pergunta e resposta)
            if question_a and answer_div:
                
                # Filtra e descarta a pergunta se houver alguma tabela na resposta
                if answer_div.find('table') is not None:
                    continue
                    
                question_text = question_a.get_text(strip=True)
                
                # Usamos separator='\n' para manter eventuais quebras de parágrafos na resposta
                answer_text = answer_div.get_text(separator='\n', strip=True)
                
                # Adiciona o dicionário (objeto) formatado na lista
                faq_list.append({
                    "id": current_id,
                    "section": section_name,
                    "question": question_text,
                    "answer": answer_text
                })
                
                current_id += 1
                
    # Salva o arquivo JSON
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(faq_list, f, ensure_ascii=False, indent=4)
        
    print(f"Scraping concluído! Foram extraídos {len(faq_list)} itens e salvos em '{DATASET_PATH}'.")

if __name__ == "__main__":
    scrape_saeb_faq()