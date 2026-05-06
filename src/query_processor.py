from src.html_parser import tokenize


class QueryProcessor:
    def clean_query(self, query: str) -> list[str]:
        return tokenize(query)

    def is_phrase_query(self, query: str) -> bool:
        query = query.strip()
        return len(query) >= 2 and query.startswith('"') and query.endswith('"')

    def extract_phrase_terms(self, query: str) -> list[str]:
        return tokenize(query.strip().strip('"'))

    def levenshtein_distance(self, first: str, second: str) -> int:
        if first == second:
            return 0

        if not first:
            return len(second)

        if not second:
            return len(first)

        previous_row = list(range(len(second) + 1))

        for i, first_char in enumerate(first, start=1):
            current_row = [i]

            for j, second_char in enumerate(second, start=1):
                insert_cost = current_row[j - 1] + 1
                delete_cost = previous_row[j] + 1
                substitute_cost = previous_row[j - 1]

                if first_char != second_char:
                    substitute_cost += 1

                current_row.append(
                    min(insert_cost, delete_cost, substitute_cost)
                )

            previous_row = current_row

        return previous_row[-1]

    def suggest_term(
        self,
        term: str,
        vocabulary: set[str],
        max_distance: int = 2,
    ) -> str | None:
        if term in vocabulary:
            return None

        candidates = []

        for vocab_term in vocabulary:
            if abs(len(vocab_term) - len(term)) > max_distance:
                continue

            distance = self.levenshtein_distance(term, vocab_term)

            if distance <= max_distance:
                candidates.append((distance, vocab_term))

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1]))

        return candidates[0][1]
