import 'dart:async';
import 'login_contract.dart';

class LoginBloc {
  /// --------------------------
  /// Streams
  /// --------------------------
  final _stateController = StreamController<LoginState>.broadcast();
  Stream<LoginState> get state => _stateController.stream;
  LoginState _currentState = LoginState();

  final _eventController = StreamController<LoginEvent>();
  Sink<LoginEvent> get eventSink => _eventController.sink;

  LoginBloc() {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(LoginEvent event) async {
    if (event is EmailChanged) {
      _currentState = _currentState.copyWith(
        email: event.email,
        emailError: event.email.contains('@') ? null : "Invalid email",
      );
      _stateController.add(_currentState);
    } else if (event is PasswordChanged) {
      _currentState = _currentState.copyWith(
        password: event.password,
        passwordError: event.password.length >= 4 ? null : "Password too short",
      );
      _stateController.add(_currentState);
    } else if (event is LoginSubmitted) {
      // Validate before submitting
      _currentState = _currentState.copyWith(
        emailError: _currentState.isEmailValid ? null : "Invalid email",
        passwordError: _currentState.isPasswordValid ? null : "Password too short",
      );
      _stateController.add(_currentState);

      if (!_currentState.canSubmit) return;

      _currentState = _currentState.copyWith(isSubmitting: true);
      _stateController.add(_currentState);

      await Future.delayed(const Duration(seconds: 3));

      if (_currentState.email == "admin@admin.com" &&
          _currentState.password == "1234") {
        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: true,
          generalError: null,
        );

      } else {
        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: false,
          generalError: "Invalid email or password",
        );
      }

      _stateController.add(_currentState);
    }
    else if (event is ClearGeneralError) {
      _currentState = _currentState.copyWith(generalError: null);
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
