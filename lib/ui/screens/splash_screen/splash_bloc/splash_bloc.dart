import 'dart:async';
import 'splash_contract.dart';

class SplashBloc {
  /// --------------------------
  /// Streams
  /// --------------------------
  final _stateController = StreamController<SplashState>.broadcast();
  Stream<SplashState> get state => _stateController.stream;
  SplashState _currentState = SplashState();

  final _eventController = StreamController<SplashEvent>();
  Sink<SplashEvent> get eventSink => _eventController.sink;

  SplashBloc() {
    _eventController.stream.listen(_mapEventToState);
  }

  void _mapEventToState(SplashEvent event) async {
    if (event is SplashStarted) {
      _currentState = _currentState.copyWith(isLoading: true, isFinished: false);
      _stateController.add(_currentState);

      // Simulate splash delay
      await Future.delayed(const Duration(seconds: 3));

      _currentState = _currentState.copyWith(isLoading: false, isFinished: true);
      _stateController.add(_currentState);
    }
  }

  void dispose() {
    _stateController.close();
    _eventController.close();
  }
}
