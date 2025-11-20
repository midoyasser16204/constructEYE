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
  final bool navigateToProfile;
  final bool navigateToSignIn;

  SplashState({
    this.isLoading = false,
    this.isFinished = false,
    this.navigateToProfile = false,
    this.navigateToSignIn = false,
  });

  SplashState copyWith({
    bool? isLoading,
    bool? isFinished,
    bool? navigateToProfile,
    bool? navigateToSignIn,
  }) {
    return SplashState(
      isLoading: isLoading ?? this.isLoading,
      isFinished: isFinished ?? this.isFinished,
      navigateToProfile: navigateToProfile ?? this.navigateToProfile,
      navigateToSignIn: navigateToSignIn ?? this.navigateToSignIn,
    );
  }
}