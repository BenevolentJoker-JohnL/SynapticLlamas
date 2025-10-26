"""
Output quality validators to catch common issues before quality voting.
Fast, rule-based checks for obvious problems.
"""

import re
import logging
from typing import Dict, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class OutputValidator:
    """Validate output quality using fast rule-based checks."""

    @staticmethod
    def check_repetition(text: str, threshold: float = 0.3) -> Tuple[bool, List[str]]:
        """
        Check for excessive repetition in text.

        Args:
            text: Text to check
            threshold: Max allowed repetition ratio (0.0 to 1.0)

        Returns:
            (passed: bool, issues: List[str])
        """
        issues = []

        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 3:
            return True, []  # Too short to check

        # Check for duplicate sentences
        sentence_counts = Counter(sentences)
        duplicates = [(sent, count) for sent, count in sentence_counts.items() if count > 1]

        if duplicates:
            total_dup_sentences = sum(count for _, count in duplicates)
            dup_ratio = total_dup_sentences / len(sentences)

            if dup_ratio > threshold:
                issues.append(f"Excessive sentence repetition: {dup_ratio:.1%} of sentences are duplicates")
                for sent, count in duplicates[:3]:  # Show top 3
                    preview = sent[:60] + "..." if len(sent) > 60 else sent
                    issues.append(f"  Repeated {count}x: \"{preview}\"")

        # Check for repeated phrases (3+ words)
        words = text.lower().split()
        if len(words) > 20:
            # Extract 3-word phrases
            phrases = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
            phrase_counts = Counter(phrases)
            common_phrases = [(phrase, count) for phrase, count in phrase_counts.items()
                            if count > 2 and not phrase.startswith(('the ', 'and ', 'of ', 'in ', 'to '))]

            if len(common_phrases) > 5:
                issues.append(f"Repetitive phrasing detected: {len(common_phrases)} phrases repeated 3+ times")
                for phrase, count in common_phrases[:2]:
                    issues.append(f"  '{phrase}' x{count}")

        passed = len(issues) == 0
        return passed, issues

    @staticmethod
    def check_length(text: str, min_words: int = 100, max_words: int = 1500) -> Tuple[bool, List[str]]:
        """
        Check if text length is reasonable.

        Args:
            text: Text to check
            min_words: Minimum word count
            max_words: Maximum word count

        Returns:
            (passed: bool, issues: List[str])
        """
        issues = []
        word_count = len(text.split())

        if word_count < min_words:
            issues.append(f"Too short: {word_count} words (min: {min_words})")
        elif word_count > max_words:
            issues.append(f"Too long: {word_count} words (max: {max_words}) - may be rambling")

        passed = len(issues) == 0
        return passed, issues

    @staticmethod
    def check_formatting(text: str) -> Tuple[bool, List[str]]:
        """
        Check for broken formatting (especially LaTeX/math).

        Args:
            text: Text to check

        Returns:
            (passed: bool, issues: List[str])
        """
        issues = []

        # Check for broken LaTeX commands (missing backslash)
        broken_latex_patterns = [
            (r'\brac\{', 'Broken \\frac command (missing backslash)'),
            (r'\bsqrt\{', 'Broken \\sqrt command (missing backslash)'),
            (r'\\dotdot', 'Broken ellipsis notation (\\dotdot should be \\dots)'),
            (r'\|[0-9a-z]+rangle', 'Broken ket notation (rangle should be ⟩ or \\rangle)'),
            (r'\\Psi_\d+\s*=\s*rac', 'Broken fraction in equation'),
        ]

        for pattern, description in broken_latex_patterns:
            if re.search(pattern, text):
                issues.append(description)

        # Check for incomplete bracket pairs
        open_brackets = text.count('|')
        close_brackets = text.count('⟩')
        if open_brackets > close_brackets + 2:  # Allow some tolerance
            issues.append(f"Incomplete bracket notation: {open_brackets} '|' but only {close_brackets} '⟩'")

        passed = len(issues) == 0
        return passed, issues

    @staticmethod
    def validate_output(text: str,
                       check_rep: bool = True,
                       check_len: bool = True,
                       check_fmt: bool = True) -> Dict:
        """
        Run all validation checks on output text.

        Args:
            text: Text to validate
            check_rep: Check for repetition
            check_len: Check length
            check_fmt: Check formatting

        Returns:
            Dict with validation results
        """
        all_issues = []
        checks_passed = 0
        checks_total = 0

        if check_rep:
            checks_total += 1
            rep_passed, rep_issues = OutputValidator.check_repetition(text)
            if rep_passed:
                checks_passed += 1
            else:
                all_issues.extend(rep_issues)

        if check_len:
            checks_total += 1
            len_passed, len_issues = OutputValidator.check_length(text)
            if len_passed:
                checks_passed += 1
            else:
                all_issues.extend(len_issues)

        if check_fmt:
            checks_total += 1
            fmt_passed, fmt_issues = OutputValidator.check_formatting(text)
            if fmt_passed:
                checks_passed += 1
            else:
                all_issues.extend(fmt_issues)

        passed = len(all_issues) == 0
        score = checks_passed / checks_total if checks_total > 0 else 1.0

        result = {
            'passed': passed,
            'score': score,
            'checks_passed': checks_passed,
            'checks_total': checks_total,
            'issues': all_issues
        }

        if passed:
            logger.info(f"✅ Output validation PASSED ({checks_passed}/{checks_total} checks)")
        else:
            logger.warning(f"⚠️  Output validation found {len(all_issues)} issue(s)")
            for issue in all_issues[:5]:  # Show first 5
                logger.warning(f"   • {issue}")

        return result
