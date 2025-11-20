import 'dart:async';
import 'package:flutter/material.dart';
import '../../../../domain/repository/AuthenticationRepository.dart';
import '../../../../domain/usecase/logout_use_case/LogOutUseCase.dart';
import '../../../../domain/usecase/get_current_user_use_case/GetCurrentUserUseCase.dart';
import 'ProfileContract.dart';

class ProfileBloc {
  final GetCurrentUserUseCase _getCurrentUserUseCase;
  final LogOutUseCase _logOutUseCase;

  final _stateController = StreamController<ProfileState>.broadcast();
  Stream<ProfileState> get state => _stateController.stream;

  ProfileState _currentState = ProfileState.initial();
  ProfileState get currentState => _currentState;

  final _eventController = StreamController<ProfileEvent>();
  Sink<ProfileEvent> get eventSink => _eventController.sink;

  ProfileBloc(this._getCurrentUserUseCase, this._logOutUseCase) {
    _eventController.stream.listen(_mapEventToState);

    // Load user when bloc is created
    _loadCurrentUser();
  }

  Future<void> _loadCurrentUser() async {
    try {
      final user = await _getCurrentUserUseCase.execute();
      if (user != null) {
        _currentState = _currentState.copyWith(
          name: user.fullName,
          email: user.email,
          phone: user.phone.toString(),
          role: user.role,
          company: user.company,
        );
        _stateController.add(_currentState);
      }
    } catch (e) {
      debugPrint("Error loading user: $e");
    }
  }

  void _mapEventToState(ProfileEvent event) async {
    if (event is TogglePushNotifications) {
      _currentState = _currentState.copyWith(pushNotifications: event.value);
      _stateController.add(_currentState);
    } else if (event is ToggleSafetyAlerts) {
      _currentState = _currentState.copyWith(safetyAlerts: event.value);
      _stateController.add(_currentState);
    } else if (event is LogoutEvent) {
      debugPrint("LOGOUT PRESSED");
      await _logOutUseCase();
      // Emit state to signal UI
      _currentState = _currentState.copyWith(isLoggedOut: true);
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}