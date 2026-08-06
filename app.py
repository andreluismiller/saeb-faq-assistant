import time
from datetime import datetime, timezone

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from saeb_faq_assistant.rag import RAGSystem
from saeb_faq_assistant import db


PAGE_TITLE = "Assistente FAQ INEP"


@st.cache_resource(show_spinner=False)
def ensure_db_ready() -> bool:
    # CREATE TABLE IF NOT EXISTS é idempotente: seguro mesmo se o init.sql
    # já tiver criado as tabelas na primeira subida do container do Postgres.
    db.init_db()
    return True


@st.cache_resource(show_spinner="Carregando o sistema RAG (modelos de embedding)...")
def load_rag_system() -> RAGSystem:
    return RAGSystem()


@st.cache_data(show_spinner=False, ttl=600)
def load_programs() -> list[str]:
    rag = load_rag_system()
    try:
        return rag.list_programs()
    except Exception:
        return []


def init_session_state():
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "feedback_given" not in st.session_state:
        st.session_state.feedback_given = False


def register_feedback(score: int):
    if st.session_state.conversation_id is None:
        return
    db.save_feedback(
        conversation_id=st.session_state.conversation_id,
        score=score,
        source="user",
    )
    st.session_state.feedback_given = True


def main():
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🎓", layout="centered")
    ensure_db_ready()
    init_session_state()

    st.markdown(
        """
        # 🎓 Assistente de FAQ do INEP
        Este assistente responde perguntas sobre as pesquisas e avaliações educacionais do INEP
        (como o Saeb) com base na base oficial de Perguntas Frequentes. Digite sua pergunta abaixo,
        opcionalmente selecione um programa específico para restringir a busca, e clique em **Perguntar**.
        """
    )

    programs = load_programs()
    program_options = ["None"] + programs

    with st.form(key="question_form"):
        question = st.text_area("Digite sua pergunta:", placeholder="Ex.: Como faço para aderir ao Saeb?")
        selected_program = st.selectbox("Programa (opcional):", options=program_options, index=0)
        submitted = st.form_submit_button("Perguntar")

    if submitted:
        if not question.strip():
            st.warning("Por favor, digite uma pergunta antes de continuar.")
        else:
            rag = load_rag_system()
            with st.spinner("Buscando e gerando resposta..."):
                try:
                    result = rag.execute_rag_pipeline(question, program=selected_program)
                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar sua pergunta: {e}")
                    result = None

            if result is not None:
                conversation_id = db.save_conversation(
                    question=result["question"],
                    answer=result["answer"],
                    course=result["program"],
                    model=result["model_used"],
                    instructions=result["instructions"],
                    prompt=result["prompt"],
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                    response_time=result["response_time_seconds"],
                    cost=result["cost_usd"],
                    timestamp=datetime.now(timezone.utc),
                )
                st.session_state.conversation_id = conversation_id
                st.session_state.last_result = result
                st.session_state.feedback_given = False

    if st.session_state.last_result is not None:
        result = st.session_state.last_result

        st.markdown("### Resposta")
        st.markdown(result["answer"])

        with st.expander("Detalhes técnicos"):
            st.write(f"**Modelo:** {result['model_used']}")
            st.write(f"**Programa filtrado:** {result['program']}")
            st.write(f"**Tempo de resposta:** {result['response_time_seconds']}s")
            st.write(
                f"**Tokens:** {result['prompt_tokens']} (prompt) + "
                f"{result['completion_tokens']} (conclusão) = {result['total_tokens']} (total)"
            )
            st.write(f"**Custo estimado:** ${result['cost_usd']:.6f}")

        st.markdown("### Essa resposta foi útil?")
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            if st.button("👍", disabled=st.session_state.feedback_given, key="thumbs_up"):
                register_feedback(score=1)
                st.rerun()
        with col2:
            if st.button("👎", disabled=st.session_state.feedback_given, key="thumbs_down"):
                register_feedback(score=-1)
                st.rerun()

        if st.session_state.feedback_given:
            st.success("Obrigado pelo seu feedback!")


if __name__ == "__main__":
    main()