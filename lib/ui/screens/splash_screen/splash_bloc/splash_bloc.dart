import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'splash_contract.dart';

/// ----------------------
/// SplashBloc (MVI)
/// ----------------------
class SplashBloc extends Bloc<SplashIntent, SplashUiState> {
  SplashBloc() : super(SplashInitial()) {
    on<SplashStarted>(_onStarted);
  }

  /// Handle SplashStarted intent
  Future<void> _onStarted(
      SplashStarted event, Emitter<SplashUiState> emit) async {
    emit(SplashLoading());

    // Delay 3 seconds (simulate splash loading)
    await Future.delayed(const Duration(seconds: 3));

    // Emit finished state
    emit(SplashFinished());
  }
}
