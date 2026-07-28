"""Versioned prompt assets. Every string an external partner can see is either
in fixed_copy_v1.py (code-owned) or produced by answer_body_v1.md's single
LLM-authored slot - there is no third source.

At production scale this directory is what migrates to Amazon Bedrock Prompt
Management; see module4-partner-support-chatbot/README.md for that
build-vs-managed decision.
"""
