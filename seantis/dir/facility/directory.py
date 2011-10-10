import json
from datetime import timedelta

from five import grok
from zope.interface import alsoProvides
from plone.namedfile.field import NamedImage
from plone.autoform.interfaces import IFormFieldProvider
from plone.directives import form
from plone.uuid.interfaces import IUUID

from seantis.dir.base import directory
from seantis.dir.base import core

from seantis.dir.facility import _

from seantis.reservation import utils
from seantis.reservation import db
from seantis.reservation import resource

class IFacilityDirectory(form.Schema):
    """Extends the seantis.dir.base.directory.IDirectory"""

    image = NamedImage(
            title=_(u'Image'),
            required=False
        )

alsoProvides(IFacilityDirectory, IFormFieldProvider)

@core.ExtendedDirectory
class FacilityDirectory(core.DirectoryMetadataBase):
    interface = IFacilityDirectory

class View(directory.View):
    grok.context(directory.IDirectory)
    grok.require('zope2.View')
    template = grok.PageTemplateFile('templates/directory.pt')

    overview_id = "seantis-overview-calendar"

    def uuids(self):
        resources = []
        for item in self.items:
            resources.extend(item.resources())
        
        return [IUUID(res) for res in resources]

    def javascript(self):
        template = """
        <script type="text/javascript">
            if (!this.seantis) this.seantis = {};
            if (!this.seantis.calendars) this.seantis.overview = [];

            this.seantis.overview.id = '#%s';
            this.seantis.overview.options = %s;

            (function($) {
                $(document).ready(function() {
                    console.log('what');
                    $(seantis.overview.id).fullCalendar(seantis.overview.options);
                });
            })( jQuery );

        </script>"""

        return template % (self.overview_id, self.calendar_options())

    def calendar_options(self):
        options = {}
        options['events'] = {
            'url': self.overview_url,
            'type': 'POST',
            'data': {
                'uuid': self.uuids()
            },
            'className': 'seantis-overview-event'
        }

        return json.dumps(options)

    @property
    def overview_url(self):
        return self.context.absolute_url_path() + '/overview'


class Overview(grok.View, resource.CalendarRequest):
    grok.context(directory.IDirectory)
    grok.require('zope2.View')
    grok.name('overview')

    def uuids(self):
        uuids = self.request.get('uuid[]', [])

        if not hasattr(uuids, '__iter__'):
            uuids = [uuids]

        return uuids

    def render(self):
        return resource.CalendarRequest.render(self)

    def events(self):
        start, end = self.range
        if not all((start, end)):
            return []

        schedulers = [db.Scheduler(uid) for uid in self.uuids()]
        if not schedulers:
            return []

        events = []
        days = (end - start).days

        for day in xrange(0, days):
            event_start = start + timedelta(days=day)
            event_end = start + timedelta(days=day+1, microseconds=-1)

            totalcount, totaloccupation = 0, 0.0
            for sc in schedulers:
                count, occupation = sc.occupation_rate(event_start, event_end)
                totalcount += count
                totaloccupation += occupation

            if not totalcount:
                continue

            average = int(totaloccupation / totalcount)
            color = utils.event_color(average)

            title = u'%i / %i%%' % (totalcount, average)

            events.append(dict(
                allDay=True,
                start=event_start.isoformat(),
                end=event_end.isoformat(),
                title=title,
                backgroundColor=color,
                borderColor=color,
            ))

        return events