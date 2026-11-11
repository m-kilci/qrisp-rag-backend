"""Offline checks for page-aware context selection; never writes the index."""

import unittest

from src.vector_store import prepare_retrieval_query, select_context_chunks


def chunk(source, index, text):
    return {"source": source, "chunk_index": index, "text": text, "score": 0.02}


class ContextSelectionTests(unittest.TestCase):
    def test_named_class_keeps_its_definition_and_example(self):
        source = "reference/generated/qrisp.Widget.run.html"
        records = [
            chunk("reference/generated/qrisp.Other.run.html", 0, "Other API"),
            chunk(source, 1, "Useful parameters"),
            chunk(source, 0, "Widget.run signature"),
            chunk(source, 2, "    Examples\n\nWidget().run()"),
        ]
        selected = select_context_chunks("How do I use `Widget`?", records)
        self.assertEqual([r["chunk_index"] for r in selected], [0, 1, 2])
        self.assertTrue(all(r["source"] == source for r in selected))

    def test_class_matching_uses_whole_name(self):
        records = [
            chunk("qrisp.QuantumVariableExtra.run.html", 0, "Wrong class"),
            chunk("qrisp.QuantumVariable.run.html", 0, "Correct class"),
        ]
        self.assertEqual(
            select_context_chunks("Use QuantumVariable", records), [records[1]],
        )

    def test_example_heading_includes_two_continuation_chunks(self):
        source = "qrisp.Widget.run.html"
        records = [
            chunk(source, 0, "Signature\nExamples\nWe create a Widget,"),
            chunk(source, 1, "```python\nw = Widget()\n```"),
            chunk(source, 2, "```python\nw.run()\n```"),
            chunk(source, 3, "Unrelated later content"),
        ]
        selected = select_context_chunks("Explain Widget.run", records)
        self.assertEqual([r["chunk_index"] for r in selected], [0, 1, 2])

    def test_example_continuations_respect_total_budget(self):
        records = [chunk("qrisp.Widget.run.html", i, text) for i, text in enumerate([
            "Definition", "Examples", "Start of code", "End of code",
        ])]
        selected = select_context_chunks("Explain Widget.run", records, top_k=3)
        self.assertEqual([r["chunk_index"] for r in selected], [0, 1, 2])
        self.assertEqual(len({(r["source"], r["chunk_index"]) for r in selected}), 3)

    def test_example_at_page_end_does_not_expand_into_another_page(self):
        records = [
            chunk("qrisp.Widget.run.html", 0, "Examples\nComplete code"),
            chunk("qrisp.Other.run.html", 0, "Other page"),
        ]
        self.assertEqual(select_context_chunks("Explain Widget.run", records), records[:1])

    def test_bare_method_includes_parent_constructor_and_example(self):
        method = "reference/generated/qrisp.Widget.run.html"
        parent = "reference/Widget.html"
        records = [
            chunk(method, 0, "Widget.run(arg): Run the operation."),
            chunk("reference/generated/qrisp.Other.run.html", 0, "Other method"),
            chunk(parent, 2, "```python\nw.run(0)\n```"),
            chunk(parent, 0, "class Widget(size=0)"),
            chunk(parent, 1, "Examples\n```python\nw = Widget(1)\n```"),
        ]
        selected = select_context_chunks("Explain Widget.run", records)
        self.assertEqual(selected[0]["source"], method)
        self.assertEqual({r["chunk_index"] for r in selected if r["source"] == parent},
                         {0, 1, 2})

    def test_method_with_example_does_not_add_parent(self):
        method = "reference/generated/qrisp.Widget.run.html"
        records = [
            chunk(method, 0, "Examples\n```python\nWidget(1).run(0)\n```"),
            chunk("reference/Widget.html", 0, "Parent class"),
        ]
        self.assertEqual(select_context_chunks("Explain Widget.run", records), records[:1])

    def test_explicit_method_call_and_qualified_name(self):
        records = [
            chunk("qrisp.Other.stop.html", 0, "Stop"),
            chunk("qrisp.Widget.run.html", 0, "Run"),
        ]
        for query in ("What does run() do?", "Explain Widget.run"):
            with self.subTest(query=query):
                self.assertEqual(select_context_chunks(query, records), [records[1]])

    def test_no_matching_identifier_falls_back_to_ranked_pages(self):
        records = [chunk("page.html", 0, "Definition\nExamples\nCode")]
        for query in ("Explain quantum simulation", "Explain UnknownClass"):
            with self.subTest(query=query):
                self.assertEqual(select_context_chunks(query, records), records)

    def test_complete_spaced_class_name_selects_its_pages(self):
        records = [
            chunk("reference/Other.html", 0, "Unrelated result"),
            chunk("reference/generated/qrisp.WidgetFactory.run.html", 0, "Method"),
            chunk("reference/WidgetFactory.html", 0, "Constructor"),
        ]
        selected = select_context_chunks("How do I use a widget factory?", records)
        self.assertEqual({r["source"] for r in selected},
                         {r["source"] for r in records[1:]})

    def test_partial_class_phrase_does_not_scope_results(self):
        records = [
            chunk("reference/Other.html", 0, "Unrelated result"),
            chunk("reference/WidgetFactory.html", 0, "Constructor"),
        ]
        self.assertEqual(select_context_chunks("Explain a factory", records), records)

    def test_spaced_phrase_does_not_override_explicit_api(self):
        records = [
            chunk("reference/WidgetFactory.html", 0, "Factory class"),
            chunk("reference/generated/qrisp.Widget.run.html", 0, "Run method"),
        ]
        selected = select_context_chunks("Explain Widget.run for a widget factory", records)
        self.assertEqual(selected, records[1:])

    def test_limits_and_deduplication(self):
        records = [chunk(f"page{i}.html", 0, "Definition\nExamples\nCode")
                   for i in range(5)]
        self.assertEqual(len(select_context_chunks("Explain", records)), 3)
        self.assertEqual(len(select_context_chunks("Explain", records, top_k=2)), 2)
        self.assertEqual(select_context_chunks("Explain", records, top_k=0), [])
        self.assertEqual(select_context_chunks("Explain", []), [])

    def test_query_preparation_keeps_substantive_instructions(self):
        question = "How do I use Widget?"
        self.assertEqual(
            prepare_retrieval_query(question + " Show a short Python example."),
            question,
        )
        substantive = question + " Show an example using a custom backend."
        self.assertEqual(prepare_retrieval_query(substantive), substantive)
        standalone = "Show a short Python example."
        self.assertEqual(prepare_retrieval_query(standalone), standalone)


if __name__ == "__main__":
    unittest.main()
