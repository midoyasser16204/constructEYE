import 'dart:async';
import 'package:validators/validators.dart';

import '../../../../domain/usecase/login_use_case/LoginUseCase.dart';
import 'LogInContract.dart';

class LoginBloc {
  final LoginUseCase _loginUseCase;

  final _stateController = StreamController<LoginState>.broadcast();
  Stream<LoginState> get state => _stateController.stream;
  LoginState _currentState = LoginState();

  final _eventController = StreamController<LoginEvent>();
  Sink<LoginEvent> get eventSink => _eventController.sink;

  LoginBloc(this._loginUseCase) {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(LoginEvent event) async {
    if (event is EmailChanged) {
      _currentState = _currentState.copyWith(
        email: event.email,
        emailError: isEmail(event.email) ? null : "Invalid email format",
      );
      _stateController.add(_currentState);
    } else if (event is PasswordChanged) {
      _currentState = _currentState.copyWith(
        password: event.password,
        passwordError: event.password.length >= 6 ? null : "Password too short",
      );
      _stateController.add(_currentState);
    } else if (event is LoginSubmitted) {
      // Validate inputs
      _currentState = _currentState.copyWith(
        emailError: isEmail(_currentState.email) ? null : "Invalid email format",
        passwordError: _currentState.password.length >= 6 ? null : "Password too short",
        generalError: null,
      );
      _stateController.add(_currentState);

      if (!_currentState.canSubmit) return;

      _currentState = _currentState.copyWith(isSubmitting: true);
      _stateController.add(_currentState);

      try {
        final user = await _loginUseCase.execute(
          _currentState.email,
          _currentState.password,
        );

        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: true,
          generalError: null,
        );
      } catch (e) {
        _currentState = _currentState.copyWith(
          isSubmitting: false,
          isSuccess: false,
          generalError: e.toString(),
        );
      }

      _stateController.add(_currentState);
    } else if (event is ClearGeneralError) {
      _currentState = _currentState.copyWith(generalError: null);
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}