import 'dart:async';
import 'package:flutter/material.dart';
import 'ProfileContract.dart';

class ProfileBloc {
  final _stateController = StreamController<ProfileState>.broadcast();
  Stream<ProfileState> get state => _stateController.stream;

  ProfileState _currentState = ProfileState(
    name: "John Doe",
    role: "Site Manager",
    email: "john.doe@constructeye.com",
    phone: "+1 (555) 123-4567",
    company: "ABC Construction Corp.",
  );

  ProfileState get currentState => _currentState;

  final _eventController = StreamController<ProfileEvent>();
  Sink<ProfileEvent> get eventSink => _eventController.sink;

  ProfileBloc() {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(ProfileEvent event) async {
    if (event is TogglePushNotifications) {
      _currentState = _currentState.copyWith(pushNotifications: event.value);
    } else if (event is ToggleSafetyAlerts) {
      _currentState = _currentState.copyWith(safetyAlerts: event.value);
    } else if (event is LogoutEvent) {
      debugPrint("LOGOUT PRESSED");
    }

    _stateController.add(_currentState);
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
