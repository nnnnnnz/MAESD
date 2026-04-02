from __future__ import annotations

from statistics import mean
from typing import List, Sequence

from .adapters import (
    GenerationRequest,
    RefinementRequest,
    StructurePredictionRequest,
    build_generation_backend,
    build_refinement_backend,
    build_structure_backend,
)
from .config import MAESDSettings
from .decision import DecisionExpert
from .ira import IntentRecognitionAgent
from .schema import DesignCandidate, DesignConstraints, DesignReport, IterationRecord
from .screening import ProteinScreeningExpert


class EvolutionaryLoop:
    def __init__(self, settings: MAESDSettings, screener: ProteinScreeningExpert, decider: DecisionExpert):
        self.settings = settings
        self.generator = build_generation_backend(settings.generation)
        self.refiner = build_refinement_backend(settings.refinement)
        self.structure_predictor = build_structure_backend(settings.structure)
        self.screener = screener
        self.decider = decider

    def run(
        self,
        constraints: DesignConstraints,
        max_iterations: int | None = None,
        population_size: int | None = None,
        stagnation_limit: int | None = None,
    ) -> DesignReport:
        max_iterations = max_iterations or self.settings.max_iterations
        population_size = population_size or self.settings.population_size
        stagnation_limit = stagnation_limit or self.settings.stagnation_limit

        population = self.generator.generate(
            GenerationRequest(constraints=constraints, population_size=population_size, seed=self.settings.seed)
        )
        history: List[IterationRecord] = []
        stagnation = 0
        previous_metrics: Sequence[float] | None = None
        stopped_reason = "max_iterations_reached"
        elite: List[DesignCandidate] = []

        for iteration in range(max_iterations):
            if iteration > 0:
                population = self.refiner.refine(
                    RefinementRequest(
                        constraints=constraints,
                        parents=elite,
                        population_size=population_size,
                        iteration=iteration,
                        seed=self.settings.seed,
                    )
                )

            for candidate in population:
                candidate.structure = self.structure_predictor.predict(
                    StructurePredictionRequest(constraints=constraints, candidate=candidate, iteration=iteration)
                )
                candidate.scores = self.screener.score(candidate, constraints)

            passed = [candidate for candidate in population if candidate.scores and self.screener.passes(candidate.scores)]
            reviewed = self.decider.review_candidates(passed if passed else population, constraints)
            elite = self.decider.pareto_front([result.candidate for result in reviewed])[: max(3, population_size // 6)]

            metrics = self._mean_metrics(passed or elite or population)
            improved = self.decider.improved(previous_metrics, metrics)
            stagnation = 0 if improved else stagnation + 1
            previous_metrics = metrics
            consensus_score = mean(float(candidate.metadata.get("decision_consensus_score", 0.0)) for candidate in (passed or elite or population))
            round_summaries = reviewed[0].rounds if reviewed else []
            feedback_digest = []
            for candidate in elite[:3]:
                feedback_digest.extend(candidate.metadata.get("feedback_digest", [])[:2])

            history.append(
                IterationRecord(
                    iteration=iteration,
                    population=len(population),
                    passed=len(passed),
                    elite=len(elite),
                    mean_structural_score=round(metrics[0], 4),
                    mean_energy_score=round(metrics[1], 4),
                    mean_functional_score=round(metrics[2], 4),
                    generation_backend=self.generator.name,
                    refinement_backend=self.refiner.name,
                    structure_backend=self.structure_predictor.name,
                    consensus_score=round(consensus_score, 4),
                    expert_rounds=round_summaries,
                    feedback_digest=list(dict.fromkeys(feedback_digest))[:6],
                )
            )

            if stagnation >= stagnation_limit:
                stopped_reason = f"stagnated_after_{iteration + 1}_iterations"
                break

        return DesignReport(
            constraints=constraints,
            best_candidates=elite,
            all_iterations=history,
            stopped_reason=stopped_reason,
            backend_summary={
                "generation": self.generator.name,
                "refinement": self.refiner.name,
                "structure": self.structure_predictor.name,
            },
        )

    def _mean_metrics(self, candidates: Sequence[DesignCandidate]) -> Sequence[float]:
        scored = [candidate.scores for candidate in candidates if candidate.scores is not None]
        if not scored:
            return (0.0, 0.0, 0.0)
        return (
            mean(score.structural_score for score in scored),
            mean(score.energy_score for score in scored),
            mean(score.functional_score for score in scored),
        )


class MAESDPipeline:
    def __init__(self, settings: MAESDSettings | None = None, seed: int | None = None):
        self.settings = settings or MAESDSettings()
        if seed is not None:
            self.settings.seed = seed
        self.ira = IntentRecognitionAgent()
        self.loop = EvolutionaryLoop(
            settings=self.settings,
            screener=ProteinScreeningExpert(),
            decider=DecisionExpert(),
        )

    def run(
        self,
        prompt: str,
        max_iterations: int | None = None,
        population_size: int | None = None,
        stagnation_limit: int | None = None,
        reference_structure_path: str | None = None,
    ) -> DesignReport:
        constraints = self.ira.parse(prompt)
        if reference_structure_path:
            constraints.reference_structure_path = reference_structure_path
        return self.loop.run(
            constraints=constraints,
            max_iterations=max_iterations,
            population_size=population_size,
            stagnation_limit=stagnation_limit,
        )
