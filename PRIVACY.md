# Easy Astro Studio Privacy Policy

**Effective date: November 7, 2026**

Easy Astro Studio is a Windows desktop application published by **Astrivanta**.
This policy explains how information is handled when you use the application,
contact us through its feedback form, or follow its external links.

For privacy questions or requests, contact **[starsandfits@gmail.com](mailto:starsandfits@gmail.com)**.

## Your astronomy files and local processing

Opening FITS files, aligning and stacking exposures, rating frames, editing,
cropping and exporting images happen on your computer. Easy Astro Studio does
not automatically upload your astronomy images, FITS headers, file paths,
projects or processing logs to Astrivanta.

FITS files can contain metadata such as observing coordinates, dates and observer
information. Saved `.astro` projects embed the loaded image and header, editing
state and references to original file paths. Exports and projects stay where you
save them. If you share those files yourself, their contents and metadata may be
visible to the recipient.

The app saves interface preferences, such as your theme, GPU preference, completion-sound preference and last selected image folder, locally under
your Windows user account. It uses temporary disk files during stacking and normally
removes them when processing ends. An interruption or system crash may leave
temporary files on your device. Uninstalling the app does not necessarily remove
images, projects or exports you saved in your own folders.

You do not need an app account for image processing. The desktop app does not
include an advertising or usage-analytics SDK or implement its own automatic
crash-reporting service.

## Optional object identification and plate solving

**Identify objects** can use existing FITS or saved-project sky coordinates and
bundled catalogs entirely on your computer. That offline method does not send
data to an external service. Catalog labels are positions of known objects,
not confirmation that those objects were detected in the image. Saved projects
can contain annotations and a plate solution (sky-coordinate metadata).

If you select **Solve with Astrometry.net (online)**, enter your own Astrometry.net
API key, check the consent box and click **Identify**, the app sends over HTTPS
to **nova.astrometry.net**:

- Your API key to authenticate with that service, followed by its session token.
- Up to 2,000 extracted star pixel positions, ranked by brightness, and the
  original image dimensions, plus solver and requested visibility/reuse settings.

The app does not send image pixels, original filenames, local paths, FITS
headers, observing dates, observer details or processing logs for this feature.
The star pattern can nevertheless reveal the imaged sky location. Astrometry.net
also receives connection information such as your IP address and request times,
and may retain submissions and results under its own service practices. The
app requests private visibility and restrictive reuse settings; these requests
do not guarantee confidentiality, deletion or a particular retention period.
Read the service information at https://astrometry.net/doc/net/api.html and your
Astrometry.net account settings before choosing to submit.

The API key is entered in a masked field and retained only for the dialog's
operation. Easy Astro Studio does not save it in app settings, projects, exported
images or logs. Do not include an API key in feedback or share it with others.

You can cancel before starting to avoid submission. Once a request is uploaded,
Cancel stops the app waiting for it and cannot recall it or stop the remote
service processing it. The app downloads the resulting sky solution and matches
it with bundled catalogs locally. Accepted labels and the sky solution can be
saved in your project; no API key or service session is included. Requests about
data held by Astrometry.net should be directed to that independent service.

## Optional bug reports and suggestions

Feedback is optional. When you open **Report a Bug / Suggest a Fix** and click
**Send**, the app sends:

- The message and report type you select.
- Your name and email address, if you enter them.
- The app name and version, and an email subject identifying the report type.

The app sends this information over HTTPS to **Formspree**, which handles the
form submission and delivery to the developer. Formspree may also process
connection information, including your IP address and request time, to operate
and protect its service. Feedback can also be stored by the email provider used
to receive and manage support messages. Images and processing logs are not
attached automatically.

We use feedback to respond when contact details are provided, investigate
problems, improve the app and maintain relevant support records. Please avoid
including passwords, payment details or other unnecessary sensitive information
in your message. Read [Formspree's privacy policy](https://formspree.io/legal/privacy-policy/)
for its handling of information.

## External links and donations

The planning link opens **https://planner.astrivanta.com** in your browser. That
website is a separate service; this policy describes the desktop application.

**Buy the Developer a Coffee** opens Cash App in your browser. If you choose to
make a donation, Cash App handles the transaction under its own policies.
Astrivanta may receive the donor identity, amount or note that Cash App makes
available to a payment recipient. The desktop app does not collect payment-card
or bank-account details. See [Cash App's privacy notice](https://cash.app/us/en/legal/privacy).

External websites and the site hosting this policy may process visit information
under their own privacy policies. Clicking an external link does not upload your
astronomy files through the app.

## Microsoft Store and Windows

Microsoft operates the Store and Windows services under its own terms,
[privacy statement](https://privacy.microsoft.com/privacystatement) and your
platform settings. Store distribution and platform diagnostics are separate
from Easy Astro Studio's local image processing and optional feedback/plate-solving features.

## Storage, retention and security

You control the local files you save and can delete them using Windows. The app
does not automatically encrypt or password-protect your saved projects or
exports; their protection depends on your device and storage settings.

Feedback is retained for responding to requests, investigating issues and
maintaining relevant support records. The desktop app does not set a fixed
automatic deletion schedule for submitted feedback. Copies may remain in
Formspree or the receiving mailbox until deleted, subject to provider/account
settings and any applicable legal requirements. You can request deletion of
information under Astrivanta's control by emailing **starsandfits@gmail.com**.

Optional feedback and online plate solving use HTTPS in transit. Formspree and email providers may store or
process submissions outside your country, including in the United States,
under their respective privacy policies and service arrangements.

## Your choices and requests

You can use the image-processing features without submitting feedback or making
a donation. Leave optional name/email fields blank if you do not want to provide
them. Close the feedback form before sending to avoid submitting its contents.

To ask about, access, correct or request deletion of feedback you previously
submitted, or to withdraw permission for further optional contact, email
**starsandfits@gmail.com**. We may need enough information to locate the message
and verify the request. Rights and exceptions depend on applicable law. Deletion
requests concern copies we control; independently operated services may have
their own request processes or legal retention requirements.

If a parent or guardian believes a child submitted personal information through
the feedback form, they can contact us at the same address to request review and
deletion.

## Changes to this policy

We may update this policy when the app or its data practices change. Updates
will be posted on this page with a revised effective date. For questions about
this policy, contact **starsandfits@gmail.com**.
