from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Source(BaseModel):
    title: str
    url: str | None = None


class AnswerSection(BaseModel):
    heading: str
    content: str


class Answer(BaseModel):
    summary: str
    sections: list[AnswerSection] = []


class RagChunk(BaseModel):
    scheme_name: str
    url: str | None = None
    score: float
    snippet: str


class AskResponse(BaseModel):
    status: str
    is_scheme_related: bool
    evidence_sufficient: bool
    reason: str | None = None
    answer: Answer | None = None
    sources: list[Source] = []
    scheme_names: list[str] = []
    retrieved_rag_data: list[RagChunk] = []
