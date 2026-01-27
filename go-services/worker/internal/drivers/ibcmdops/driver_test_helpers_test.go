package ibcmdops

import "context"

type fakeStorage struct {
	resolveInputRequested string
	resolveInputResolved  string
	resolveInputCleanup   func()
	resolveInputErr       error

	prepareRequestedPath string
	prepareOutputPath    string
	prepareArtifactPath  string
	prepareFinalize      func(ctx context.Context) error
	prepareCleanup       func()
	prepareErr           error
}

func (s *fakeStorage) ResolveInput(_ context.Context, inputPath string) (string, func(), error) {
	s.resolveInputRequested = inputPath
	if s.resolveInputCleanup == nil {
		s.resolveInputCleanup = func() {}
	}
	return s.resolveInputResolved, s.resolveInputCleanup, s.resolveInputErr
}

func (s *fakeStorage) PrepareOutput(_ context.Context, outputPath, _ string, _ string) (string, string, func(ctx context.Context) error, func(), error) {
	s.prepareRequestedPath = outputPath
	if s.prepareFinalize == nil {
		s.prepareFinalize = func(context.Context) error { return nil }
	}
	if s.prepareCleanup == nil {
		s.prepareCleanup = func() {}
	}
	return s.prepareOutputPath, s.prepareArtifactPath, s.prepareFinalize, s.prepareCleanup, s.prepareErr
}
