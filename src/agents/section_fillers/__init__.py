"""Section Fillers — LLM-powered content generators for variable slides.

Each filler generates content for ONE proposal section, producing
ManifestEntry objects with injection_data ready for renderer_v2.
Template-owned content (A1 clones, pool clones) is NOT generated here —
only b_variable slides that require RFP-specific LLM content.
"""
