// lib/ui/screens/projects_screen/projects_bloc/projects_contract.dart

import 'package:flutter/material.dart';

/// -----------------------------
/// 🔹 Events (User Actions)
/// -----------------------------
abstract class ProjectsEvent {}

class LoadProjects extends ProjectsEvent {}

class SearchQueryChanged extends ProjectsEvent {
  final String query;
  SearchQueryChanged(this.query);
}

/// -----------------------------
/// 🔹 Project Model (Fake Model)
/// -----------------------------
class ProjectModel {
  final String title;
  final String location;
  final int progress;
  final String status;
  final String imagePath;

  ProjectModel({
    required this.title,
    required this.location,
    required this.progress,
    required this.status,
    required this.imagePath,
  });
}

/// -----------------------------
/// 🔹 State (UI State)
/// -----------------------------
class ProjectsState {
  final List<ProjectModel> allProjects;
  final List<ProjectModel> filteredProjects;
  final String searchQuery;
  final bool isLoading;
  final String? generalError;

  ProjectsState({
    this.allProjects = const [],
    this.filteredProjects = const [],
    this.searchQuery = '',
    this.isLoading = false,
    this.generalError,
  });

  ProjectsState copyWith({
    List<ProjectModel>? allProjects,
    List<ProjectModel>? filteredProjects,
    String? searchQuery,
    bool? isLoading,
    String? generalError,
  }) {
    return ProjectsState(
      allProjects: allProjects ?? this.allProjects,
      filteredProjects: filteredProjects ?? this.filteredProjects,
      searchQuery: searchQuery ?? this.searchQuery,
      isLoading: isLoading ?? this.isLoading,
      generalError: generalError,
    );
  }
}