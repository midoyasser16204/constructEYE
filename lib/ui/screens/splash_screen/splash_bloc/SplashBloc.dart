import 'dart:async';
import '../../../../data/data_source/shared_pref/SharedPrefDataSource.dart';
import '../../../../domain/repository/AuthenticationRepository.dart';
import 'SplashContract.dart';

class SplashBloc {
  final SharedPrefDataSource _sharedPref;

  /// --------------------------
  /// Streams
  /// --------------------------
  final _stateController = StreamController<SplashState>.broadcast();
  Stream<SplashState> get state => _stateController.stream;
  SplashState _currentState = SplashState();

  final _eventController = StreamController<SplashEvent>();
  Sink<SplashEvent> get eventSink => _eventController.sink;

  SplashBloc(this._sharedPref) {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(SplashEvent event) async {
    if (event is SplashStarted) {
      _currentState = _currentState.copyWith(isLoading: true, isFinished: false);
      _stateController.add(_currentState);

      // Simulate splash delay
      await Future.delayed(const Duration(seconds: 2));

      // Check if user is logged in via SharedPreferences
      final uid = _sharedPref.getUid();

      if (uid != null && uid.isNotEmpty) {
        // User is logged in → go to Profile
        _currentState = _currentState.copyWith(
          isLoading: false,
          isFinished: true,
          navigateToProfile: true,
        );
      } else {
        // User not logged in → go to SignIn
        _currentState = _currentState.copyWith(
          isLoading: false,
          isFinished: true,
          navigateToSignIn: true,
        );
      }

      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}