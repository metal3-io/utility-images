package copilotreview

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/sirupsen/logrus"

	prowconfig "sigs.k8s.io/prow/pkg/config"
	prowgithub "sigs.k8s.io/prow/pkg/github"
	"sigs.k8s.io/prow/pkg/pluginhelp"
)

const PluginName = "copilot-review"

var (
	CopilotReviewRe  = regexp.MustCompile(`(?mi)^/copilot-review\s*$`)
	mustBeAuthorized = "You must be a member of the %s GitHub org to request a Copilot review."
	isNotPR          = "`/copilot-review` can only be used on pull requests."
)

type githubClient interface {
	CreateComment(owner, repo string, number int, comment string) error
	IsMember(org, user string) (bool, error)
}

// HelpProvider returns the plugin help for external plugin registration.
func HelpProvider(_ []prowconfig.OrgRepo) (*pluginhelp.PluginHelp, error) {
	pluginHelp := &pluginhelp.PluginHelp{
		Description: "The copilot-review plugin allows members of the GitHub org to request a GitHub Copilot code review on a pull request by commenting `/copilot-review`. It uses a shared org token so users without their own Copilot seat can still trigger a review.",
	}
	pluginHelp.AddCommand(pluginhelp.Command{
		Usage:       "/copilot-review",
		Description: "Requests a GitHub Copilot code review on the pull request.",
		Featured:    false,
		WhoCanUse:   "Members of the GitHub org.",
		Examples:    []string{"/copilot-review"},
	})
	return pluginHelp, nil
}

// Handle processes a GenericCommentEvent for the /copilot-review command.
func Handle(gc githubClient, log *logrus.Entry, e *prowgithub.GenericCommentEvent, dryRun bool) error {
	if e.Action != prowgithub.GenericCommentActionCreated {
		return nil
	}

	if !CopilotReviewRe.MatchString(e.Body) {
		return nil
	}

	org := e.Repo.Owner.Login
	repo := e.Repo.Name

	// Only works on pull requests
	if !e.IsPR {
		return gc.CreateComment(org, repo, e.Number, isNotPR)
	}

	// Check authorization: commenter must be a member of the org
	allowed, err := isAllowed(gc, org, e.User.Login)
	if err != nil {
		log.WithError(err).Error("Failed to check if author is an org member.")
		return err
	}
	if !allowed {
		return gc.CreateComment(org, repo, e.Number, fmt.Sprintf(mustBeAuthorized, org))
	}

	// Request Copilot review via gh CLI using the shared org token
	if dryRun {
		log.Infof("[dry-run] Would request Copilot review on %s/%s#%d", org, repo, e.Number)
		return nil
	}
	if err := RequestCopilotReview(org, repo, e.Number); err != nil {
		log.WithError(err).Errorf("Failed to request Copilot review on %s/%s#%d", org, repo, e.Number)
		return gc.CreateComment(org, repo, e.Number, "Failed to request Copilot review.")
	}

	log.Infof("Copilot review requested on %s/%s#%d by %s", org, repo, e.Number, e.User.Login)
	return gc.CreateComment(org, repo, e.Number,
		fmt.Sprintf("Copilot code review has been requested by @%s. Please allow a few moments for the review to be added.", e.User.Login))
}

func GHToken() string {
	// Based on https://cli.github.com/manual/gh_help_environment
	// GH_TOKEN takes precedence over GITHUB_TOKEN,
	// but also check COPILOT_REVIEW_TOKEN for explicit configuration.
	if t := os.Getenv("COPILOT_REVIEW_TOKEN"); t != "" {
		return t
	} else if t := os.Getenv("GH_TOKEN"); t != "" {
		return t
	}
	return os.Getenv("GITHUB_TOKEN")
}

// isAllowed checks whether the user is authorized to use the plugin.
// TODO: create a check to verify person requesting has lgtm or approval
// right in the repo. lgtm plugin could be a useful reference for this,
// but it uses some prow internal code, so it can not just be copied here.
func isAllowed(gc githubClient, org, login string) (bool, error) {
	return gc.IsMember(org, login)
}

// RequestCopilotReview shells out to gh CLI to add @copilot as a reviewer.
// It is a variable so tests can replace it with a stub.
var RequestCopilotReview = requestCopilotReview

func requestCopilotReview(org, repo string, prNumber int) error {
	token := GHToken()
	if token == "" {
		return fmt.Errorf("no GitHub token configured for Copilot review (set COPILOT_REVIEW_TOKEN, GH_TOKEN or GITHUB_TOKEN)")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	// Opens a subprocess to run `gh pr edit` to add @copilot as a reviewer,
	// using the token for authentication. Strip out GH_TOKEN from the environment.
	// This process only requires the token for the review request API call. This way
	// it is possible to have other GH CLI commands authenticated with a different token if
	// needed without affecting the plugin's ability to request reviews.
	cmd := exec.CommandContext(ctx, "gh", "pr", "edit", strconv.Itoa(prNumber),
		"--repo", fmt.Sprintf("%s/%s", org, repo),
		"--add-reviewer", "@copilot")
	env := make([]string, 0, len(os.Environ()))
	for _, e := range os.Environ() {
		if !strings.HasPrefix(e, "GH_TOKEN=") && !strings.HasPrefix(e, "GITHUB_TOKEN=") {
			env = append(env, e)
		}
	}
	cmd.Env = append(env, "GH_TOKEN="+token)
	output, err := cmd.CombinedOutput()
	if ctx.Err() == context.DeadlineExceeded {
		return fmt.Errorf("gh pr edit timed out after 30s")
	}
	if err != nil {
		return fmt.Errorf("gh pr edit failed: %w, output: %s", err, string(output))
	}
	return nil
}
