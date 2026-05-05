package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/sirupsen/logrus"

	"sigs.k8s.io/prow/pkg/config/secret"
	"sigs.k8s.io/prow/pkg/flagutil"
	prowgithub "sigs.k8s.io/prow/pkg/github"
	"sigs.k8s.io/prow/pkg/interrupts"
	"sigs.k8s.io/prow/pkg/logrusutil"
	"sigs.k8s.io/prow/pkg/pjutil"
	"sigs.k8s.io/prow/pkg/pluginhelp/externalplugins"

	copilotreview "prow-plugin-copilot-review/copilot-review"
)

type options struct {
	port                   int
	dryRun                 bool
	github                 flagutil.GitHubOptions
	instrumentationOptions flagutil.InstrumentationOptions
	webhookSecretFile      string
}

func (o *options) Validate() error {
	for _, group := range []flagutil.OptionGroup{&o.github, &o.instrumentationOptions} {
		if err := group.Validate(o.dryRun); err != nil {
			return err
		}
	}
	return nil
}

func gatherOptions() options {
	o := options{}
	fs := flag.NewFlagSet(os.Args[0], flag.ExitOnError)
	fs.IntVar(&o.port, "port", 8888, "Port to listen on.")
	fs.BoolVar(&o.dryRun, "dry-run", true, "Dry run for testing. Uses API tokens but does not mutate.")
	fs.StringVar(&o.webhookSecretFile, "hmac-secret-file", "/etc/webhook/hmac", "Path to the file containing the GitHub HMAC secret.")
	for _, group := range []flagutil.OptionGroup{&o.github, &o.instrumentationOptions} {
		group.AddFlags(fs)
	}
	fs.Parse(os.Args[1:])
	return o
}

func main() {
	o := gatherOptions()
	if err := o.Validate(); err != nil {
		logrus.Fatalf("Invalid options: %v", err)
	}

	logrusutil.ComponentInit()
	log := logrus.StandardLogger().WithField("plugin", copilotreview.PluginName)

	if err := secret.Add(o.webhookSecretFile); err != nil {
		logrus.WithError(err).Fatal("Error starting secrets agent.")
	}

	githubClient, err := o.github.GitHubClient(o.dryRun)
	if err != nil {
		logrus.WithError(err).Fatal("Error getting GitHub client.")
	}

	serv := &server{
		tokenGenerator: secret.GetTokenGenerator(o.webhookSecretFile),
		ghc:            githubClient,
		log:            log,
		dryRun:         o.dryRun,
	}

	health := pjutil.NewHealthOnPort(o.instrumentationOptions.HealthPort)
	health.ServeReady()

	mux := http.NewServeMux()
	mux.Handle("/", serv)
	externalplugins.ServeExternalPluginHelp(mux, log, copilotreview.HelpProvider)
	httpServer := &http.Server{
		Addr:         ":" + strconv.Itoa(o.port),
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}
	defer interrupts.WaitForGracefulShutdown()
	interrupts.ListenAndServe(httpServer, 5*time.Second)
}

type server struct {
	tokenGenerator func() []byte
	ghc            prowgithub.Client
	log            *logrus.Entry
	dryRun         bool
}

func (s *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	eventType, eventGUID, payload, ok, status := prowgithub.ValidateWebhook(w, r, s.tokenGenerator)
	if !ok {
		s.log.WithField(prowgithub.EventGUID, eventGUID).Errorf("Error validating webhook. Got status code %d.", status)
		return
	}

	fmt.Fprint(w, "Event received.")

	// Only handle top-level issue/PR comments. Review thread comments
	// ("pull_request_review_comment") are not supported.
	if eventType != "issue_comment" {
		return
	}

	var ic prowgithub.IssueCommentEvent
	if err := json.Unmarshal(payload, &ic); err != nil {
		s.log.WithError(err).WithField(prowgithub.EventGUID, eventGUID).Error("Error unmarshalling event.")
		return
	}

	go func() {
		if err := s.handleIssueComment(ic); err != nil {
			s.log.WithError(err).WithField(prowgithub.EventGUID, eventGUID).Error("Handling copilot-review failed.")
		}
	}()
}

func (s *server) handleIssueComment(ic prowgithub.IssueCommentEvent) error {
	e := &prowgithub.GenericCommentEvent{
		Action:     prowgithub.GenericCommentEventAction(ic.Action),
		IsPR:       ic.Issue.IsPullRequest(),
		Body:       ic.Comment.Body,
		Number:     ic.Issue.Number,
		Repo:       ic.Repo,
		User:       ic.Comment.User,
		ID:         ic.Comment.ID,
		IssueState: ic.Issue.State,
	}
	return copilotreview.Handle(s.ghc, s.log, e, s.dryRun)
}
