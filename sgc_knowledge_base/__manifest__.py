{
    "name": "SGC Knowledge Base for All Personas",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Generic searchable knowledge base (PDF, DOCX, TXT) for any AI assistant",
    "description": """
Provides a generic knowledge‑base model that ingests PDF/DOCX/TXT files, extracts plain‑text, creates vector embeddings via the FreeLLM API, and exposes an LLM tool `search_knowledge_documents`.
Assistants (AML, Finance, HR, etc.) can call the tool with optional tag filters to retrieve relevant document snippets.
""",
    "author": "SGC TECH AI",
    "website": "https://www.sgctech.ai",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "llm"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/tool_data.xml"
    ],
    "installable": True,
    "auto_install": False
}
