import base64
import json
import logging
import os
import re
import tempfile
from datetime import datetime

import requests

_logger = logging.getLogger(__name__)

_RESUME_SYSTEM_PROMPT = """You are a resume parser. Extract structured information from the resume text below.
Return ONLY valid JSON. No preamble, no markdown fences, no commentary.

Schema:
{
    "candidate_name": "...",
    "email": "...",
    "phone": "...",
    "linkedin": "...",
    "current_role": "...",
    "current_company": "...",
    "total_experience_years": 0,
    "skills": ["..."],
    "experience": [
        {"company": "...", "role": "...", "duration": "...", "description": "..."}
    ],
    "education": [
        {"degree": "...", "institution": "...", "year": "..."}
    ],
    "certifications": [],
    "salary_expectation": null,
    "availability": null,
    "summary": ""
}
Use null for missing strings/numbers, empty array [] for missing arrays."""


def extract_text(attachment_data):
    """Extract plain text from an attachment (PDF, TXT, or fallback raw decode).

    attachment_data: tuple (filename, base64_content, mimetype, ...)
    """
    filename = attachment_data[0]
    content_b64 = attachment_data[1]
    content = base64.b64decode(content_b64)
    ext = os.path.splitext(filename)[1].lower()

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    try:
        with open(tmp_path, 'wb') as f:
            f.write(content)

        if ext == '.pdf':
            import fitz
            doc = fitz.open(tmp_path)
            text = '\n'.join(page.get_text() for page in doc)
            doc.close()
            return text.strip()

        if ext in ('.docx',):
            try:
                from zipfile import ZipFile
                from xml.etree import ElementTree
                with ZipFile(tmp_path) as z:
                    xml_content = z.read('word/document.xml')
                tree = ElementTree.fromstring(xml_content)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                text = '\n'.join(
                    t.text for t in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                    if t.text
                )
                return text.strip()
            except Exception:
                pass

        mime = attachment_data[2] if len(attachment_data) > 2 else ''
        if mime.startswith('text/') or ext in ('.txt', '.html', '.htm', '.rtf'):
            return content.decode('utf-8', errors='replace').strip()

        return content.decode('utf-8', errors='replace').strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _call_llm(system_prompt, user_text):
    """Call Groq LLM directly for resume parsing."""
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        _logger.error('GROQ_API_KEY not set')
        return None

    try:
        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            json={
                'model': 'llama-3.1-8b-instant',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_text[:15000]},
                ],
                'max_tokens': 2048,
                'temperature': 0.1,
            },
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            timeout=90,
        )
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']
        reply = re.sub(r'^```(?:json)?\s*\n?', '', reply.strip())
        reply = re.sub(r'\n?```\s*$', '', reply)
        return json.loads(reply)
    except Exception as e:
        _logger.error('LLM resume parse failed: %s', e)
        return None


def parse_resume(text):
    """Parse resume text → structured JSON dict."""
    return _call_llm(_RESUME_SYSTEM_PROMPT, text)


def map_to_applicant(parsed):
    """Map parsed resume JSON → hr.applicant write() values."""
    vals = {}

    if parsed.get('candidate_name'):
        vals['partner_name'] = parsed['candidate_name'][:256]
    if parsed.get('email'):
        vals['email_from'] = parsed['email']
    if parsed.get('phone'):
        vals['partner_phone'] = parsed['phone'][:64]
    if parsed.get('linkedin'):
        vals['linkedin_profile'] = parsed['linkedin'][:1024]
    if parsed.get('salary_expectation'):
        try:
            vals['salary_expected'] = float(parsed['salary_expectation'])
        except (ValueError, TypeError):
            pass
    if parsed.get('availability'):
        try:
            vals['availability'] = datetime.strptime(parsed['availability'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    # Custom fields for precise mapping
    if parsed.get('current_role'):
        vals['candidate_current_role'] = parsed['current_role'][:256]
    if parsed.get('current_company'):
        vals['candidate_current_company'] = parsed['current_company'][:256]
    if parsed.get('total_experience_years'):
        try:
            vals['candidate_experience_years'] = float(parsed['total_experience_years'])
        except (ValueError, TypeError):
            pass
    if parsed.get('skills'):
        vals['candidate_skills'] = '\n'.join(parsed['skills'])
    if parsed.get('certifications'):
        certs = parsed['certifications']
        if certs and isinstance(certs[0], dict):
            vals['candidate_certifications'] = '\n'.join(
                f"{c.get('name', '')} — {c.get('issuer', '') or c.get('provider', '')}"
                if c.get('issuer') or c.get('provider') else c.get('name', '')
                for c in certs
            )
        else:
            vals['candidate_certifications'] = '\n'.join(str(c) for c in certs)
    if parsed.get('experience'):
        lines = []
        for exp in parsed['experience']:
            role = exp.get('role', '')
            company = exp.get('company', '')
            duration = exp.get('duration', '')
            desc = exp.get('description', '')
            lines.append(f'• {role} at {company} ({duration})')
            if desc:
                lines.append(f'  {desc}')
        vals['candidate_experience'] = '\n'.join(lines)
    if parsed.get('education'):
        lines = []
        for edu in parsed['education']:
            degree = edu.get('degree', '')
            institution = edu.get('institution', '')
            year = edu.get('year', '')
            lines.append(f'• {degree} — {institution} ({year})')
        vals['candidate_education'] = '\n'.join(lines)
    if parsed.get('availability') and isinstance(parsed['availability'], str):
        vals['candidate_availability'] = parsed['availability'][:256]

    # Keep applicant_notes as rich HTML for quick view
    parts = []
    if parsed.get('summary'):
        parts.append(f'<p><strong>Summary:</strong> {parsed["summary"]}</p>')
    if parsed.get('skills'):
        parts.append(f'<p><strong>Skills:</strong> {", ".join(parsed["skills"])}</p>')

    if parsed.get('experience'):
        html = '<p><strong>Experience:</strong></p><ul>'
        for exp in parsed['experience']:
            html += f'<li><strong>{exp.get("role", "")}</strong> at {exp.get("company", "")} ({exp.get("duration", "")})'
            if exp.get('description'):
                html += f'<br/>{exp["description"]}'
            html += '</li>'
        html += '</ul>'
        parts.append(html)

    if parsed.get('education'):
        html = '<p><strong>Education:</strong></p><ul>'
        for edu in parsed['education']:
            html += f'<li>{edu.get("degree", "")} — {edu.get("institution", "")} ({edu.get("year", "")})</li>'
        html += '</ul>'
        parts.append(html)

    if parsed.get('certifications'):
        certs = parsed['certifications']
        if certs and isinstance(certs[0], dict):
            cert_labels = [
                f"{c.get('name', '')} ({c.get('issuer', '') or c.get('provider', '')})"
                if c.get('issuer') or c.get('provider') else c.get('name', '')
                for c in certs
            ]
        else:
            cert_labels = [str(c) for c in certs]
        parts.append(f'<p><strong>Certifications:</strong> {", ".join(cert_labels)}</p>')

    if parsed.get('current_role') and parsed.get('current_company'):
        parts.append(f'<p><strong>Current:</strong> {parsed["current_role"]} at {parsed["current_company"]}</p>')

    if parts:
        vals['applicant_notes'] = '\n'.join(parts)

    return vals


def process_attachment(env, applicant_id, attachment_data):
    """Full pipeline: extract text → LLM parse → map → write on applicant."""
    _logger.info('Processing resume for applicant %s from %s', applicant_id, attachment_data[0])
    try:
        text = extract_text(attachment_data)
        if not text:
            _logger.warning('No text extracted from %s', attachment_data[0])
            return False

        parsed = parse_resume(text)
        if not parsed:
            _logger.warning('LLM parse returned nothing for %s', attachment_data[0])
            return False

        vals = map_to_applicant(parsed)
        if not vals:
            _logger.info('No fields to update for applicant %s', applicant_id)
            return False

        env['hr.applicant'].browse(applicant_id).write(vals)
        _logger.info('Wrote resume data to applicant %s: %s', applicant_id, list(vals.keys()))
        return True
    except Exception as e:
        _logger.error('Resume processing failed for applicant %s: %s', applicant_id, e)
        return False
