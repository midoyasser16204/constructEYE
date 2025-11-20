// lib/ui/screens/projects_screen/projects_bloc/projects_bloc.dart

import 'dart:async';
import 'projectscontract.dart';

class ProjectsBloc {
  final _stateController = StreamController<ProjectsState>.broadcast();
  Stream<ProjectsState> get state => _stateController.stream;

  ProjectsState _currentState = ProjectsState();

  final _eventController = StreamController<ProjectsEvent>();
  Sink<ProjectsEvent> get eventSink => _eventController.sink;

  ProjectsBloc() {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(ProjectsEvent event) async {
    if (event is LoadProjects) {
      _currentState = _currentState.copyWith(isLoading: true);
      _stateController.add(_currentState);

      await Future.delayed(const Duration(milliseconds: 500));

      final fakeData = [
        ProjectModel(
          title: "Downtown Plaza",
          location: "Manhattan, NY",
          progress: 75,
          status: "On Track",
          imagePath: "assets/images/p1.png",
        ),
        ProjectModel(
          title: "Riverside Towers",
          location: "Brooklyn, NY",
          progress: 45,
          status: "Active",
          imagePath: "assets/images/p2.png",
        ),
        ProjectModel(
          title: "Tech Campus",
          location: "San Jose, CA",
          progress: 92,
          status: "Final Phase",
          imagePath: "assets/images/p3.png",
        ),
        ProjectModel(
          title: "Harbor Bridge",
          location: "Seattle, WA",
          progress: 30,
          status: "In Progress",
          imagePath: "assets/images/p4.png",
        ),
      ];

      _currentState = _currentState.copyWith(
        allProjects: fakeData,
        filteredProjects: fakeData,
        isLoading: false,
      );

      _stateController.add(_currentState);
    }

    else if (event is SearchQueryChanged) {
      final query = event.query.toLowerCase();

      final filtered = _currentState.allProjects.where((project) {
        return project.title.toLowerCase().contains(query) ||
               project.location.toLowerCase().contains(query);
      }).toList();

      _currentState = _currentState.copyWith(
        searchQuery: event.query,
        filteredProjects: filtered,
      );

      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
