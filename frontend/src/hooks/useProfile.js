import { useState, useEffect, useCallback } from "react";
import { getProfile } from "../api/profile";
import { listSkills, createSkill, updateSkill, deleteSkill } from "../api/skills";
import { listProjects, createProject, updateProject, deleteProject } from "../api/projects";

export function useProfile() {
  const [profile, setProfile] = useState(null);
  const [skills, setSkills] = useState([]);
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [profData, skillsData, projectsData] = await Promise.all([
        getProfile().catch(() => null),
        listSkills().catch(() => []),
        listProjects().catch(() => []),
      ]);
      setProfile(profData);
      setSkills(skillsData || []);
      setProjects(projectsData || []);
    } catch (err) {
      setError(err.message || "Failed to load profile data.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const addSkill = async (skillData) => {
    setError(null);
    try {
      const newSkill = await createSkill(skillData);
      setSkills((prev) => [...prev, newSkill]);
      setSuccessMessage(`Skill "${newSkill.name}" added successfully.`);
      return newSkill;
    } catch (err) {
      setError(err.message || "Failed to add skill.");
      throw err;
    }
  };

  const editSkill = async (skillId, skillData) => {
    setError(null);
    try {
      const updated = await updateSkill(skillId, skillData);
      setSkills((prev) => prev.map((s) => (s.id === skillId ? updated : s)));
      setSuccessMessage(`Skill "${updated.name}" updated successfully.`);
      return updated;
    } catch (err) {
      setError(err.message || "Failed to update skill.");
      throw err;
    }
  };

  const removeSkill = async (skillId) => {
    setError(null);
    try {
      await deleteSkill(skillId);
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
      setSuccessMessage("Skill deleted successfully.");
    } catch (err) {
      setError(err.message || "Failed to delete skill.");
      throw err;
    }
  };

  const addProject = async (projectData) => {
    setError(null);
    try {
      const newProj = await createProject(projectData);
      setProjects((prev) => [newProj, ...prev]);
      setSuccessMessage(`Project "${newProj.name}" created successfully.`);
      return newProj;
    } catch (err) {
      setError(err.message || "Failed to create project.");
      throw err;
    }
  };

  const editProject = async (projectId, projectData) => {
    setError(null);
    try {
      const updated = await updateProject(projectId, projectData);
      setProjects((prev) => prev.map((p) => (p.id === projectId ? updated : p)));
      setSuccessMessage(`Project "${updated.name}" updated successfully.`);
      return updated;
    } catch (err) {
      setError(err.message || "Failed to update project.");
      throw err;
    }
  };

  const removeProject = async (projectId) => {
    setError(null);
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
      setSuccessMessage("Project deleted successfully.");
    } catch (err) {
      setError(err.message || "Failed to delete project.");
      throw err;
    }
  };

  return {
    profile,
    skills,
    projects,
    isLoading,
    error,
    successMessage,
    loadData,
    addSkill,
    editSkill,
    removeSkill,
    addProject,
    editProject,
    removeProject,
    clearError: () => setError(null),
    clearSuccess: () => setSuccessMessage(null),
  };
}
