import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Settings:
    data: Path = field(default_factory=lambda: Path(os.getenv('DOCINT_DATA', 'data')))
    token: str = field(default_factory=lambda: os.getenv('DOCINT_TOKEN', ''))
    extractor: str = field(default_factory=lambda: os.getenv('DOCINT_EXTRACTOR', 'rules'))
    embeddings: str = field(default_factory=lambda: os.getenv('DOCINT_EMBEDDINGS', 'fastembed'))
    llm_url: str = field(default_factory=lambda: os.getenv('DOCINT_LLM_URL', 'http://127.0.0.1:11434/v1/chat/completions'))
    llm_model: str = field(default_factory=lambda: os.getenv('DOCINT_LLM_MODEL', 'qwen2.5:7b'))
    llm_key: str = field(default_factory=lambda: os.getenv('DOCINT_LLM_KEY', ''))
    llm_schema: bool = field(default_factory=lambda: os.getenv('DOCINT_LLM_SCHEMA', '0')=='1')
    max_mb: int = field(default_factory=lambda: int(os.getenv('DOCINT_MAX_MB', '30')))
    max_units: int = field(default_factory=lambda: int(os.getenv('DOCINT_MAX_UNITS', '1500')))
    job_seconds: int = field(default_factory=lambda: int(os.getenv('DOCINT_JOB_SECONDS', '3600')))
    worker: bool = True
    def __post_init__(self):
        if self.extractor not in {'rules','llm'}:
            raise ValueError('DOCINT_EXTRACTOR must be rules or llm')
        if self.embeddings not in {'fastembed','off'}:
            raise ValueError('DOCINT_EMBEDDINGS must be fastembed or off')
        if min(self.max_mb,self.max_units,self.job_seconds)<=0:
            raise ValueError('Processing limits must be positive')
