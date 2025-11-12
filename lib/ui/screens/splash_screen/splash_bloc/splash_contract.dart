/// This file defines the Splash “contract” — Events (Intents) and UI States

import 'package:equatable/equatable.dart';

/// ----------------------
/// 1️⃣ Intents (Events)
/// ----------------------
abstract class SplashIntent extends Equatable {
  const SplashIntent();

  @override
  List<Object> get props => [];
}

/// Triggered when Splash starts
class SplashStarted extends SplashIntent {}

/// ----------------------
/// 2️⃣ UI States
/// ----------------------
abstract class SplashUiState extends Equatable {
  const SplashUiState();

  @override
  List<Object> get props => [];
}

/// Initial state
class SplashInitial extends SplashUiState {}

/// Loading / waiting state
class SplashLoading extends SplashUiState {}

/// Finished state — ready to navigate
class SplashFinished extends SplashUiState {}
