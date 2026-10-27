import { useState, useEffect, useCallback } from "react";
import {
  getOpenPlacements,
  getPlacementPriorities,
  getUpcomingPlacements,
  getPlacementComparison,
  prepareForPlacement,
} from "../api/placements";

export function usePlacements() {
  const [openDrives, setOpenDrives] = useState([]);
  const [priorities, setPriorities] = useState([]);
  const [upcomingDrives, setUpcomingDrives] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Modal / detail states
  const [selectedComparison, setSelectedComparison] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [preparationPlan, setPreparationPlan] = useState(null);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [openData, priorityData, upcomingData] = await Promise.all([
        getOpenPlacements(),
        getPlacementPriorities(),
        getUpcomingPlacements(30),
      ]);
      setOpenDrives(openData || []);
      setPriorities(priorityData || []);
      setUpcomingDrives(upcomingData || []);
    } catch (err) {
      console.error("Failed to load placement intelligence data:", err);
      setError(err.message || "Failed to load placement data");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadComparison = async (placementId) => {
    setIsComparing(true);
    try {
      const comp = await getPlacementComparison(placementId);
      setSelectedComparison(comp);
    } catch (err) {
      console.error("Failed to load placement comparison:", err);
      setError(err.message || "Failed to load placement comparison");
    } finally {
      setIsComparing(false);
    }
  };

  const generatePlan = async (placementId) => {
    setIsGeneratingPlan(true);
    try {
      const plan = await prepareForPlacement(placementId);
      setPreparationPlan(plan);
    } catch (err) {
      console.error("Failed to generate preparation plan:", err);
      setError(err.message || "Failed to generate preparation plan");
    } finally {
      setIsGeneratingPlan(false);
    }
  };

  const closeModals = () => {
    setSelectedComparison(null);
    setPreparationPlan(null);
  };

  return {
    openDrives,
    priorities,
    upcomingDrives,
    isLoading,
    error,
    refresh: loadData,
    selectedComparison,
    isComparing,
    loadComparison,
    preparationPlan,
    isGeneratingPlan,
    generatePlan,
    closeModals,
  };
}
