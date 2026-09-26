from app.agents.tools.adapters import BaseToolAdapter, ToolResult
from app.agents.tools.job_search import job_search, JobSearchAdapter, JobSearchToolInput
from app.agents.tools.render_docx import render_docx, RenderDocxAdapter, RenderDocxInput
from app.agents.tools.resume_extractor import resume_extractor, ResumeExtractorAdapter, ResumeExtractInput
from app.agents.tools.scraper import scrape_website, ScraperAdapter, ScrapeInput
from app.agents.tools.web_search import web_search, WebSearchAdapter, WebSearchInput

TOOL_REGISTRY: dict[str, BaseToolAdapter] = {
    "web_search": web_search,
    "scrape_website": scrape_website,
    "job_search": job_search,
    "resume_extractor": resume_extractor,
    "render_docx": render_docx,
}

__all__ = [
    "TOOL_REGISTRY", "BaseToolAdapter", "ToolResult",
    "web_search", "scrape_website", "job_search", "resume_extractor", "render_docx",
]
