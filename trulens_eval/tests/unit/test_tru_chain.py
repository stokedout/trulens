"""
Tests for TruChain. This is outdated.
"""

import unittest
from unittest import main
from unittest import TestCase

import pinecone
import torch
from transformers import AutoModelForCausalLM
from transformers import AutoTokenizer
from transformers import pipeline

from trulens_eval.keys import check_keys
from trulens_eval.tru_chain import TruChain
from trulens_eval.util import OptionalImports
from trulens_eval.util import REQUIREMENT_LANGCHAIN

check_keys(
    "OPENAI_API_KEY", "HUGGINGFACE_API_KEY", "PINECONE_API_KEY", "PINECONE_ENV"
)

with OptionalImports(message=REQUIREMENT_LANGCHAIN):
    from langchain import LLMChain
    from langchain import PromptTemplate
    from langchain.chains import ConversationalRetrievalChain
    from langchain.chains import SimpleSequentialChain
    from langchain.embeddings.openai import OpenAIEmbeddings
    from langchain.llms import HuggingFacePipeline
    from langchain.memory import ConversationBufferWindowMemory
    from langchain.vectorstores import Pinecone


class TestTruChain(TestCase):

    def setUp(self):
        print("setup")

        self.llm_model_id = "gpt2"
        # This model is pretty bad but using it for tests because it is free and
        # relatively small.

        # model_id = "decapoda-research/llama-7b-hf"
        # model_id = "decapoda-research/llama-13b-hf"

        self.model = AutoModelForCausalLM.from_pretrained(
            self.llm_model_id,
            device_map='auto',
            torch_dtype=torch.float16,
            local_files_only=True
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.llm_model_id, local_files_only=True
        )

        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=16,
            device_map="auto",
            early_stopping=True
        )

        self.llm = HuggingFacePipeline(pipeline=self.pipe)

    @unittest.skip("TODO")
    async def test_async(self):
        import asyncio

        from langchain import PromptTemplate
        from langchain.callbacks import AsyncIteratorCallbackHandler
        from langchain.chains import LLMChain
        from langchain.chat_models.openai import ChatOpenAI

        from trulens_eval import feedback
        from trulens_eval import Feedback
        from trulens_eval import Tru

        class AsyncAgent:

            def __init__(self):
                tru = Tru()
                hugs = feedback.Huggingface()
                f_lang_match = Feedback(hugs.language_match).on_input_output()

                self.async_callback = AsyncIteratorCallbackHandler()
                prompt = PromptTemplate.from_template(
                    """Honestly answer this question: {question}."""
                )
                llm = ChatOpenAI(
                    streaming=True, callbacks=[self.async_callback]
                )
                self.agent = LLMChain(llm=llm, prompt=prompt)
                self.agent = tru.Chain(
                    self.agent,
                    app_id='smalltalk_agent',
                    feedbacks=[f_lang_match]
                )

            async def respond_each_token(self, message):
                f_res_record = asyncio.create_task(
                    self.agent.acall_with_record(
                        inputs=dict(question=message),
                    )
                )

                async for token in self.async_callback.aiter():
                    yield token

                self.res, self.record = await f_res_record

        # TODO: async test cases?
        st = AsyncAgent()
        async for tok in st.respond_each_token(
                "What is 1+2? Explain your answer."):
            print(tok)

    @unittest.skip("outdated")
    def test_qa_prompt(self):
        # Test of a small q/a app using a prompt and a single call to an llm.

        # llm = OpenAI()

        template = """Q: {question} A:"""
        prompt = PromptTemplate(template=template, input_variables=["question"])
        llm_app = LLMChain(prompt=prompt, llm=self.llm)

        tru_app = TruChain(app=llm_app)

        assert tru_app.app is not None

        tru_app.run(dict(question="How are you?"))
        tru_app.run(dict(question="How are you today?"))

        assert len(tru_app.db.select()) == 2

    @unittest.skip("outdated")
    def test_qa_prompt_with_memory(self):
        # Test of a small q/a app using a prompt and a single call to an llm.
        # Also has memory.

        # llm = OpenAI()

        template = """Q: {question} A:"""
        prompt = PromptTemplate(template=template, input_variables=["question"])

        memory = ConversationBufferWindowMemory(k=2)

        llm_app = LLMChain(prompt=prompt, llm=self.llm, memory=memory)

        tru_app = TruChain(app=llm_app)

        assert tru_app.app is not None

        tru_app.run(dict(question="How are you?"))
        tru_app.run(dict(question="How are you today?"))

        assert len(tru_app.db.select()) == 2

    @unittest.skip("outdated")
    def test_qa_db(self):
        # Test a q/a app that uses a vector store to look up context to include in
        # llm prompt.

        # WARNING: this test incurs calls to pinecone and openai APIs and may cost money.

        index_name = "llmdemo"

        embedding = OpenAIEmbeddings(
            model='text-embedding-ada-002'
        )  # 1536 dims

        pinecone.init(
            api_key=os.environ.get('PINECONE_API_KEY'
                                  ),  # find at app.pinecone.io
            environment=os.environ.get('PINECONE_ENV'
                                      )  # next to api key in console
        )
        docsearch = Pinecone.from_existing_index(
            index_name=index_name, embedding=embedding
        )

        # llm = OpenAI(temperature=0,max_tokens=128)

        retriever = docsearch.as_retriever()
        app = ConversationalRetrievalChain.from_llm(
            llm=self.llm, retriever=retriever, return_source_documents=True
        )

        tru_app = TruChain(app)
        assert tru_app.app is not None
        tru_app(dict(question="How do I add a model?", chat_history=[]))

        assert len(tru_app.db.select()) == 1

    @unittest.skip("outdated")
    def test_sequential(self):
        # Test of a sequential app that contains the same llm twice with
        # different prompts.

        template = """Q: {question} A:"""
        prompt = PromptTemplate(template=template, input_variables=["question"])
        llm_app = LLMChain(prompt=prompt, llm=self.llm)

        template_2 = """Reverse this sentence: {sentence}."""
        prompt_2 = PromptTemplate(
            template=template_2, input_variables=["sentence"]
        )
        llm_app_2 = LLMChain(prompt=prompt_2, llm=self.llm)

        seq_app = SimpleSequentialChain(
            apps=[llm_app, llm_app_2],
            input_key="question",
            output_key="answer"
        )
        seq_app.run(
            question="What is the average air speed velocity of a laden swallow?"
        )

        tru_app = TruChain(seq_app)
        assert tru_app.app is not None

        # This run should not be recorded.
        seq_app.run(
            question="What is the average air speed velocity of a laden swallow?"
        )

        # These two should.
        tru_app.run(
            question=
            "What is the average air speed velocity of a laden european swallow?"
        )
        tru_app.run(
            question=
            "What is the average air speed velocity of a laden african swallow?"
        )

        assert len(tru_app.db.select()) == 2


if __name__ == '__main__':
    main()
