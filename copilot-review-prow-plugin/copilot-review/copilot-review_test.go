package copilotreview

import (
	"errors"
	"fmt"
	"testing"

	"github.com/sirupsen/logrus"
	prowgithub "sigs.k8s.io/prow/pkg/github"
)

func TestCopilotReviewRegex(t *testing.T) {
	tests := []struct {
		input string
		match bool
	}{
		{"/copilot-review", true},
		{"/copilot-review\n", true},
		{"/copilot-review  ", true},
		{"  /copilot-review", false},
		{"/copilot-review-foo", false},
		{"some text /copilot-review", false},
		{"LGTM\n/copilot-review\nthanks", true},
		{"/Copilot-Review", true},
		{"/copilot-review\n/approve", true},
		{"", false},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := CopilotReviewRe.MatchString(tt.input)
			if got != tt.match {
				t.Errorf("CopilotReviewRe.MatchString(%q) = %v, want %v", tt.input, got, tt.match)
			}
		})
	}
}

func TestHelpProvider(t *testing.T) {
	help, err := HelpProvider(nil)
	if err != nil {
		t.Fatalf("HelpProvider returned error: %v", err)
	}
	if help == nil {
		t.Fatal("HelpProvider returned nil")
	}
	if help.Description == "" {
		t.Error("HelpProvider returned empty description")
	}
}

func TestGHToken(t *testing.T) {
	// COPILOT_REVIEW_TOKEN takes precedence
	t.Setenv("COPILOT_REVIEW_TOKEN", "copilot-tok")
	t.Setenv("GH_TOKEN", "gh-tok")
	t.Setenv("GITHUB_TOKEN", "github-tok")
	if got := GHToken(); got != "copilot-tok" {
		t.Errorf("expected copilot-tok, got %s", got)
	}

	// GH_TOKEN is next
	t.Setenv("COPILOT_REVIEW_TOKEN", "")
	if got := GHToken(); got != "gh-tok" {
		t.Errorf("expected gh-tok, got %s", got)
	}

	// GITHUB_TOKEN is fallback
	t.Setenv("GH_TOKEN", "")
	if got := GHToken(); got != "github-tok" {
		t.Errorf("expected github-tok, got %s", got)
	}

	// Empty when nothing set
	t.Setenv("GITHUB_TOKEN", "")
	if got := GHToken(); got != "" {
		t.Errorf("expected empty, got %s", got)
	}
}

// fakeGitHubClient records calls for assertions.
type fakeGitHubClient struct {
	comments   []string
	isMember   bool
	memberErr  error
	commentErr error
}

func (f *fakeGitHubClient) CreateComment(_, _ string, _ int, comment string) error {
	f.comments = append(f.comments, comment)
	return f.commentErr
}

func (f *fakeGitHubClient) IsMember(_, _ string) (bool, error) {
	return f.isMember, f.memberErr
}

func TestHandle(t *testing.T) {
	baseEvent := func() *prowgithub.GenericCommentEvent {
		return &prowgithub.GenericCommentEvent{
			Action: prowgithub.GenericCommentActionCreated,
			Body:   "/copilot-review",
			IsPR:   true,
			Number: 42,
			Repo: prowgithub.Repo{
				Owner: prowgithub.User{Login: "metal3-io"},
				Name:  "test-repo",
			},
			User: prowgithub.User{Login: "testuser"},
		}
	}

	tests := []struct {
		name            string
		event           func() *prowgithub.GenericCommentEvent
		client          *fakeGitHubClient
		dryRun          bool
		reviewErr       error
		expectErr       bool
		expectComments  []string
		expectReviewReq bool
	}{
		{
			name: "ignores non-created actions",
			event: func() *prowgithub.GenericCommentEvent {
				e := baseEvent()
				e.Action = prowgithub.GenericCommentActionDeleted
				return e
			},
			client:          &fakeGitHubClient{isMember: true},
			expectComments:  nil,
			expectReviewReq: false,
		},
		{
			name: "ignores comments without command",
			event: func() *prowgithub.GenericCommentEvent {
				e := baseEvent()
				e.Body = "just a normal comment"
				return e
			},
			client:          &fakeGitHubClient{isMember: true},
			expectComments:  nil,
			expectReviewReq: false,
		},
		{
			name: "rejects non-PR comments",
			event: func() *prowgithub.GenericCommentEvent {
				e := baseEvent()
				e.IsPR = false
				return e
			},
			client:         &fakeGitHubClient{isMember: true},
			expectComments: []string{isNotPR},
		},
		{
			name:           "rejects non-org members",
			event:          baseEvent,
			client:         &fakeGitHubClient{isMember: false},
			expectComments: []string{fmt.Sprintf(mustBeAuthorized, "metal3-io")},
		},
		{
			name:      "returns error when IsMember fails",
			event:     baseEvent,
			client:    &fakeGitHubClient{memberErr: errors.New("API error")},
			expectErr: true,
		},
		{
			name:            "dry-run skips review request and comment",
			event:           baseEvent,
			client:          &fakeGitHubClient{isMember: true},
			dryRun:          true,
			expectComments:  nil,
			expectReviewReq: false,
		},
		{
			name:            "posts success comment on successful review request",
			event:           baseEvent,
			client:          &fakeGitHubClient{isMember: true},
			expectReviewReq: true,
			expectComments:  []string{"Copilot code review has been requested by @testuser. Please allow a few moments for the review to be added."},
		},
		{
			name:            "posts failure comment when review request fails",
			event:           baseEvent,
			client:          &fakeGitHubClient{isMember: true},
			reviewErr:       errors.New("gh CLI failed"),
			expectReviewReq: true,
			expectComments:  []string{"Failed to request Copilot review."},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			reviewRequested := false
			origRequestCopilotReview := RequestCopilotReview
			RequestCopilotReview = func(_, _ string, _ int) error {
				reviewRequested = true
				return tt.reviewErr
			}
			t.Cleanup(func() { RequestCopilotReview = origRequestCopilotReview })

			log := logrus.NewEntry(logrus.New())
			err := Handle(tt.client, log, tt.event(), tt.dryRun)

			if tt.expectErr && err == nil {
				t.Fatal("expected error, got nil")
			}
			if !tt.expectErr && err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tt.expectReviewReq && !reviewRequested {
				t.Error("expected review request, but it was not made")
			}
			if !tt.expectReviewReq && reviewRequested {
				t.Error("did not expect review request, but it was made")
			}
			if len(tt.expectComments) != len(tt.client.comments) {
				t.Fatalf("expected %d comments, got %d: %v", len(tt.expectComments), len(tt.client.comments), tt.client.comments)
			}
			for i, want := range tt.expectComments {
				if tt.client.comments[i] != want {
					t.Errorf("comment[%d] = %q, want %q", i, tt.client.comments[i], want)
				}
			}
		})
	}
}
