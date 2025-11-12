/// --------------------------
/// 🔹 Splash Events
/// --------------------------
abstract class SplashEvent {}

/// Triggered when splash screen starts
class SplashStarted extends SplashEvent {}

/// --------------------------
/// 🔹 Splash State
/// --------------------------
class SplashState {
  final bool isLoading;
  final bool isFinished;

  SplashState({
    this.isLoading = false,
    this.isFinished = false,
  });

  SplashState copyWith({
    bool? isLoading,
    bool? isFinished,
  }) {
    return SplashState(
      isLoading: isLoading ?? this.isLoading,
      isFinished: isFinished ?? this.isFinished,
    );
  }
}
