# -*- coding: utf-8 -*-
"""Main knowledge‑document model.

Key features:
- Stores the original binary file (PDF/DOCX/TXT) as an attachment.
- Extracts plain‑text with PyMuPDF / python‑docx.
- Calls the FreeLLM embedding endpoint → stores JSON‑encoded vector (BYTEA).
- Provides a tool method `search_knowledge_documents` for LLM agents.
"""

import base64, json, logging, os, requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SgcKnowledgeDocument(models.Model):
    _name = 'sgc.knowledge.document'
    _description = 'Generic Knowledge‑Base Document'

    name = fields.Char(string='Title', required=True)
    file = fields.Binary(string='File', attachment=True, required=True)
    mimetype = fields.Char(string='MIME type')
    content = fields.Text(string='Extracted Text', readonly=True)
    embedding = fields.Binary(string='Embedding (json‑bytes)', readonly=True)
    tag_ids = fields.Many2many(
        comodel_name='sgc.knowledge.tag',
        string='Tags',
        help='Add tags (e.g. "aml", "finance", "hr") to filter searches.'
    )

    # -----------------------------------------------------------------
    # Creation / write hooks – automatically extract & embed
    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._process_file()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('file'):
            for rec in self:
                rec._process_file()
        return res

    # -----------------------------------------------------------------
    # Text extraction – PDF, DOCX, fallback to UTF‑8 decode
    # -----------------------------------------------------------------
    def _extract_text(self, raw, mimetype):
        import io
        if mimetype == 'application/pdf':
            import fitz  # PyMuPDF
            doc = fitz.open(stream=raw, filetype='pdf')
            return "\n".join(page.get_text() for page in doc)
        elif mimetype in (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/msword',
        ):
            from docx import Document
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        else:
            try:
                return raw.decode('utf-8')
            except Exception:
                return ""

    # -----------------------------------------------------------------
    # Embedding via FreeLLM (or any compatible service)
    # -----------------------------------------------------------------
    def _fetch_embedding(self, text):
        headers = {
            "Authorization": f"Bearer {os.getenv('FREELLM_API_KEY')}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "text-embedding-ada-002",  # adjust to your provider
            "input": text[:2000],
        }
        try:
            resp = requests.post(
                f"{os.getenv('FREELLM_API_URL')}/embeddings",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get('data', [{}])[0].get('embedding')
        except Exception as e:
            _logger.exception('Failed to fetch embedding for document %s', self.name)
            return None

    # -----------------------------------------------------------------
    # Main processing pipeline – called on create/write
    # -----------------------------------------------------------------
    def _process_file(self):
        if not self.file:
            return
        raw = base64.b64decode(self.file)
        txt = self._extract_text(raw, self.mimetype or '')
        self.content = txt[:5000]  # preview
        embed = self._fetch_embedding(txt)
        if embed:
            # Store as JSON string in BYTEA – later cast to vector on‑fly
            self.embedding = json.dumps(embed).encode('utf-8')
        else:
            self.embedding = False

    # -----------------------------------------------------------------
    # Public LLM tool – similarity search with optional tag filter
    # -----------------------------------------------------------------
    @api.model
    def search_knowledge_documents(self, query, tags=False, limit=5):
        """Tool entry point.
        * `query` – free‑text user question.
        * `tags` – optional list of tag *names* to narrow the search.
        Returns a list of dicts: {title, snippet}.
        """
        embed = self._fetch_embedding(query)
        if not embed:
            return []

        # Build optional tag filter clause
        where_clause = ""
        params = [json.dumps(embed), limit]
        if tags:
            where_clause = """
                AND id IN (
                    SELECT doc_id FROM sgc_knowledge_document_tag_rel rel
                    JOIN sgc.knowledge.tag t ON rel.tag_id = t.id
                    WHERE t.name = ANY(%s)
                )
            """
            params.insert(1, tags)  # tags become second param

        sql = f"""
            SELECT id, name, content
            FROM sgc_knowledge_document
            ORDER BY embedding::vector <=> %s::vector
            {where_clause}
            LIMIT %s
        """
        self.env.cr.execute(sql, tuple(params))
        rows = self.env.cr.fetchall()
        out = []
        for _id, title, txt in rows:
            snippet = (txt or "")[:200].replace('\n', ' ').strip()
            out.append({
                'title': title,
                'snippet': snippet + ('…' if len(txt or '') > 200 else '')
            })
        return out

    # -----------------------------------------------------------------
    # Helper for nightly re‑indexing (optional cron)
    # -----------------------------------------------------------------
    def _reindex_all(self):
        for rec in self.search([]):
            rec._process_file()
