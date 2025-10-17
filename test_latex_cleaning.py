#!/usr/bin/env python3
"""Test LaTeX cleaning function"""

import sys
sys.path.insert(0, '.')
from agents.base_agent import clean_broken_latex

# Test broken LaTeX from actual output
broken_text = """The total Hilbert space for the two-particle system given the tensor product these spaces Τπε. The wave function χ_ (x_A x_B) describing the state of the bipartite system can be written as a linear combination basis states χ_ (x_A x_B) ×± i angle ×± j angle where c are the coefficients of the expansion and |x_A i angle and |x_B j angle are the basis states for particles A and B respectively.

The coefficients can be obtained applying measurement to particle which collapses the wave function onto one of the possible outcomes ϗ_ |χ_ (x_A x_B)×ε_x_B！π|χ_ (x_A x_B)πε_x_B angle. The reduced density matrix for particle B given ϗ_B Tr_A ϗ where Tr_A denotes the partial trace over system A and taking the expectation value operator in this space can calculate the correlation between particles A and B."""

print("BEFORE CLEANING:")
print("=" * 80)
print(broken_text)
print("\n")

cleaned_text = clean_broken_latex(broken_text)

print("AFTER CLEANING:")
print("=" * 80)
print(cleaned_text)
print("\n")

print("KEY FIXES:")
print("  Τπε → H⊗H (Hilbert space tensor product)")
print("  χ_ → ψ (wave function)")
print("  ×± i angle → Σ |i⟩ (summation over ket)")
print("  ϗ → ρ (density matrix)")
print("  ！ → (removed)")
